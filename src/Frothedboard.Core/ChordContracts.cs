namespace Frothedboard.Core;

/// <summary>A single physical key transition, as reported by the low-level hook.</summary>
/// <param name="VirtualKey">Windows virtual-key code.</param>
/// <param name="IsDown">True for key-down, false for key-up.</param>
/// <param name="IsRepeat">True when this down-event came from auto-repeat rather than a fresh press.</param>
/// <param name="TimestampMs">Monotonic milliseconds. Drives every timeout in the machine.</param>
public readonly record struct KeyEvent(int VirtualKey, bool IsDown, bool IsRepeat, long TimestampMs)
{
    public static KeyEvent Down(int vk, long t, bool repeat = false) => new(vk, true, repeat, t);
    public static KeyEvent Up(int vk, long t) => new(vk, false, false, t);
}

public enum EffectKind
{
    /// <summary>A native copy is about to land. Snapshot the current clipboard and watch for the update.</summary>
    ArmCopyCapture,

    /// <summary>Discard the armed snapshot — the chord did not complete. Nothing to undo.</summary>
    CancelCopyCapture,

    /// <summary>Store the just-copied payload into <see cref="Effect.Slot"/>, then restore the armed snapshot.</summary>
    CaptureToSlot,

    /// <summary>Put <see cref="Effect.Slot"/> on the clipboard, send Ctrl+V, then restore the system clipboard.</summary>
    PasteFromSlot,

    /// <summary>Emit the deferred ordinary paste as a synthetic Ctrl+V.</summary>
    SendNativePaste,
}

public readonly record struct Effect(EffectKind Kind, int Slot = -1)
{
    public static Effect ArmCopy() => new(EffectKind.ArmCopyCapture);
    public static Effect CancelCopy() => new(EffectKind.CancelCopyCapture);
    public static Effect Capture(int slot) => new(EffectKind.CaptureToSlot, slot);
    public static Effect Paste(int slot) => new(EffectKind.PasteFromSlot, slot);
    public static Effect NativePaste() => new(EffectKind.SendNativePaste);
}

/// <summary>
/// What the shim must do about one key event: whether to swallow it, and any clipboard
/// work to perform. Effects are ordered and must be executed in order.
/// </summary>
public readonly record struct ChordResult(bool Suppress, IReadOnlyList<Effect> Effects)
{
    private static readonly Effect[] None = [];

    /// <summary>Let the key reach the foreground app untouched. The overwhelming majority of keystrokes.</summary>
    public static readonly ChordResult PassThrough = new(false, None);

    /// <summary>Swallow the key so the foreground app never sees it.</summary>
    public static readonly ChordResult Swallow = new(true, None);

    public static ChordResult Pass(params Effect[] effects) => new(false, effects);
    public static ChordResult Suppressed(params Effect[] effects) => new(true, effects);
}

public sealed record FrothedConfig
{
    /// <summary>Ten frothed boards, addressed by the digit you press, on top of the untouched
    /// system clipboard. Eleven places to put things in total.</summary>
    public int SlotCount { get; init; } = 10;

    /// <summary>How long after a native Ctrl+C a digit still counts as part of the chord.</summary>
    public int CopyChordTimeoutMs { get; init; } = 1500;

    /// <summary>
    /// Hang guard only. The ordinary paste normally fires on Ctrl release or on the next key,
    /// so this is deliberately long: a short timer would fire the paste and then paste a second
    /// time if the user hesitated and then tapped a digit.
    /// </summary>
    public int PasteBackstopMs { get; init; } = 2000;

    /// <summary>How long to wait for the clipboard to actually change after a native copy.</summary>
    public int ClipboardSettleTimeoutMs { get; init; } = 400;

    /// <summary>Delay before restoring the system clipboard after a slot paste, for apps that read it lazily.</summary>
    public int PasteRestoreDelayMs { get; init; } = 250;

    /// <summary>Whether Ctrl+X takes the chord as well as Ctrl+C.</summary>
    public bool EnableCut { get; init; } = true;
}
