namespace Frothedboard.Core.Tests;

/// <summary>
/// Scripts a sequence of physical keystrokes through the machine and records exactly what the
/// Win32 shim would have been told to do: which keys reached the app, which were swallowed,
/// and which clipboard effects fired, in order.
/// </summary>
internal sealed class Driver(FrothedConfig? config = null)
{
    private readonly ChordStateMachine _machine = new(config);
    private long _now;

    public List<Effect> Effects { get; } = [];
    public List<(int Vk, bool Down)> Swallowed { get; } = [];
    public List<(int Vk, bool Down)> Passed { get; } = [];

    public ChordStateMachine.State State => _machine.Current;
    public IEnumerable<EffectKind> Kinds => Effects.Select(e => e.Kind);

    public Driver Advance(long ms)
    {
        _now += ms;
        return this;
    }

    public Driver Down(int vk, bool repeat = false) => Feed(KeyEvent.Down(vk, _now, repeat));

    public Driver Up(int vk) => Feed(KeyEvent.Up(vk, _now));

    /// <summary>A realistic press-and-release, with a few milliseconds of contact time.</summary>
    public Driver Tap(int vk) => Down(vk).Advance(6).Up(vk).Advance(6);

    public Driver Tick()
    {
        Effects.AddRange(_machine.Tick(_now).Effects);
        return this;
    }

    public Driver Reset()
    {
        Effects.AddRange(_machine.Reset().Effects);
        return this;
    }

    public int Count(EffectKind kind) => Effects.Count(e => e.Kind == kind);

    public int SlotOf(EffectKind kind) => Effects.Single(e => e.Kind == kind).Slot;

    public bool WasSwallowed(int vk, bool down = true) => Swallowed.Contains((vk, down));

    public bool WasPassed(int vk, bool down = true) => Passed.Contains((vk, down));

    private Driver Feed(KeyEvent e)
    {
        var result = _machine.Process(e);
        (result.Suppress ? Swallowed : Passed).Add((e.VirtualKey, e.IsDown));
        Effects.AddRange(result.Effects);
        _now += 2;
        return this;
    }
}
