namespace Frothedboard.Core;

/// <summary>
/// Decides what a keystroke means while Ctrl is held. Pure logic, no Win32, no clipboard —
/// the platform shim feeds it hook events and executes the effects it returns.
///
/// Copy and paste are deliberately asymmetric:
///
/// * Ctrl+C passes straight through, so an ordinary copy is untouched and costs nothing extra.
///   If a digit follows while Ctrl is still down, the payload that just landed on the clipboard
///   is moved into that slot and the previous clipboard is put back.
///
/// * Ctrl+V is swallowed, because a paste cannot be taken back. It fires the moment Ctrl comes
///   up (tens of milliseconds for a human) or the moment a digit arrives — a release, not a timer.
/// </summary>
public sealed class ChordStateMachine
{
    public enum State
    {
        Idle,

        /// <summary>A native copy has just been let through; a digit now diverts it to a slot.</summary>
        AwaitCopySlot,

        /// <summary>A paste has been swallowed and is owed to the user.</summary>
        AwaitPasteSlot,
    }

    private readonly FrothedConfig _config;

    private State _state = State.Idle;
    private long _armedAt;

    /// <summary>Keys whose key-down we swallowed, so their key-up goes too and no app sees a stray release.</summary>
    private readonly HashSet<int> _swallowedDowns = [];

    private bool _lCtrl, _rCtrl, _lShift, _rShift, _lAlt, _rAlt, _lWin, _rWin;

    public ChordStateMachine(FrothedConfig? config = null) => _config = config ?? new FrothedConfig();

    public State Current => _state;
    public bool CtrlHeld => _lCtrl || _rCtrl;

    private bool OtherModifierHeld => _lShift || _rShift || _lAlt || _rAlt || _lWin || _rWin;

    /// <summary>Ctrl and nothing else. Ctrl+Shift+V and Ctrl+Alt+V must behave exactly as they always did.</summary>
    private bool BareCtrl => CtrlHeld && !OtherModifierHeld;

    /// <summary>Feed one hook event. Injected events must be filtered out by the caller before this point.</summary>
    public ChordResult Process(KeyEvent e)
    {
        if (Vk.IsModifier(e.VirtualKey))
            return ProcessModifier(e);

        // The key-up of anything we swallowed has to go too. Checked ahead of everything else so
        // it survives the state having already moved on.
        if (!e.IsDown && _swallowedDowns.Remove(e.VirtualKey))
            return ChordResult.Swallow;

        if (!e.IsDown)
            return ChordResult.PassThrough;

        // A stale chord closes itself out, and its closing effect rides along with this event.
        Effect? expiry = null;
        if (_state != State.Idle && e.TimestampMs - _armedAt > TimeoutFor(_state))
            expiry = CloseState();

        var result = _state switch
        {
            State.AwaitCopySlot => InCopyChord(e),
            State.AwaitPasteSlot => InPasteChord(e),
            _ => FromIdle(e),
        };

        return Prepend(expiry, result);
    }

    /// <summary>
    /// Safety net for a chord left open with no further keys — a Ctrl key physically stuck down,
    /// or a missed key-up after a focus change. Call from a timer.
    /// </summary>
    public ChordResult Tick(long nowMs)
    {
        if (_state == State.Idle || nowMs - _armedAt <= TimeoutFor(_state))
            return ChordResult.PassThrough;

        var effect = CloseState();
        return effect is null ? ChordResult.PassThrough : ChordResult.Pass(effect.Value);
    }

    /// <summary>
    /// Drop all tracked key state, e.g. on desktop switch or hook reinstall. Any paste we still
    /// owe the user is returned rather than silently discarded.
    /// </summary>
    public ChordResult Reset()
    {
        var effect = CloseState();
        _lCtrl = _rCtrl = _lShift = _rShift = _lAlt = _rAlt = _lWin = _rWin = false;
        _swallowedDowns.Clear();
        return effect is null ? ChordResult.PassThrough : ChordResult.Pass(effect.Value);
    }

    private ChordResult ProcessModifier(KeyEvent e)
    {
        bool ctrlWasHeld = CtrlHeld;
        SetModifier(e.VirtualKey, e.IsDown);

        if (!ctrlWasHeld || CtrlHeld)
            return ChordResult.PassThrough;

        // Ctrl just came up. This is the disambiguator the whole design rests on.
        switch (_state)
        {
            case State.AwaitPasteSlot:
                _state = State.Idle;
                // The real Ctrl-up goes through first; the shim then synthesises a complete Ctrl+V.
                return ChordResult.Pass(Effect.NativePaste());

            case State.AwaitCopySlot:
                _state = State.Idle;
                return ChordResult.Pass(Effect.CancelCopy());

            default:
                return ChordResult.PassThrough;
        }
    }

    private ChordResult InCopyChord(KeyEvent e)
    {
        int slot = SlotFor(e.VirtualKey);
        if (slot >= 0 && CtrlHeld)
        {
            _state = State.Idle;
            return SwallowDown(e.VirtualKey, Effect.Capture(slot));
        }

        // Anything else abandons the chord. The native copy has already happened, so there is
        // nothing to undo and no way for this to bite the user.
        _state = State.Idle;
        return Prepend(Effect.CancelCopy(), FromIdle(e));
    }

    private ChordResult InPasteChord(KeyEvent e)
    {
        int slot = SlotFor(e.VirtualKey);
        if (slot >= 0 && CtrlHeld)
        {
            _state = State.Idle;
            return SwallowDown(e.VirtualKey, Effect.Paste(slot));
        }

        // Another V without releasing Ctrl — a deliberate burst or auto-repeat. Flush the one we
        // owe and defer this one in its place, so N presses still yield N pastes, in order.
        if (e.VirtualKey == Vk.V && BareCtrl)
        {
            _armedAt = e.TimestampMs;
            return SwallowDown(e.VirtualKey, Effect.NativePaste());
        }

        // Any other key: the paste we owe has to land before it.
        _state = State.Idle;
        return Prepend(Effect.NativePaste(), FromIdle(e));
    }

    private ChordResult FromIdle(KeyEvent e)
    {
        if (!BareCtrl)
            return ChordResult.PassThrough;

        if (e.VirtualKey == Vk.C || (_config.EnableCut && e.VirtualKey == Vk.X))
        {
            _state = State.AwaitCopySlot;
            _armedAt = e.TimestampMs;
            // Passes through — the real copy happens now, at full speed.
            return ChordResult.Pass(Effect.ArmCopy());
        }

        if (e.VirtualKey == Vk.V)
        {
            _state = State.AwaitPasteSlot;
            _armedAt = e.TimestampMs;
            // Swallowed — a paste cannot be taken back, so this one waits for the Ctrl release.
            return SwallowDown(e.VirtualKey);
        }

        return ChordResult.PassThrough;
    }

    private ChordResult SwallowDown(int vk, params Effect[] effects)
    {
        _swallowedDowns.Add(vk);
        return new ChordResult(true, effects);
    }

    private int SlotFor(int vk)
    {
        int slot = Vk.ToSlot(vk);
        return slot < _config.SlotCount ? slot : -1;
    }

    private int TimeoutFor(State state) => state switch
    {
        State.AwaitCopySlot => _config.CopyChordTimeoutMs,
        State.AwaitPasteSlot => _config.PasteBackstopMs,
        _ => int.MaxValue,
    };

    private Effect? CloseState()
    {
        var state = _state;
        _state = State.Idle;
        return state switch
        {
            State.AwaitCopySlot => Effect.CancelCopy(),
            State.AwaitPasteSlot => Effect.NativePaste(),
            _ => null,
        };
    }

    private static ChordResult Prepend(Effect? first, ChordResult rest) =>
        first is null ? rest : new ChordResult(rest.Suppress, [first.Value, .. rest.Effects]);

    private void SetModifier(int vk, bool down)
    {
        switch (vk)
        {
            case Vk.LControl or Vk.Control: _lCtrl = down; break;
            case Vk.RControl: _rCtrl = down; break;
            case Vk.LShift or Vk.Shift: _lShift = down; break;
            case Vk.RShift: _rShift = down; break;
            case Vk.LAlt or Vk.Alt: _lAlt = down; break;
            case Vk.RAlt: _rAlt = down; break;
            case Vk.LWin: _lWin = down; break;
            case Vk.RWin: _rWin = down; break;
        }
    }
}
