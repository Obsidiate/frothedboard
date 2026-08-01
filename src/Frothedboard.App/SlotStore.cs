namespace Frothedboard.App;

/// <summary>
/// The ten frothed boards. The system clipboard is the eleventh and is not stored here — it stays
/// where Windows keeps it, untouched.
///
/// Memory only, on purpose. Nothing a board holds is ever written to disk, so quitting the app
/// takes everything you copied with it. That rules out persistence across restarts, which is the
/// intended trade: a clipboard tool that quietly spools whatever you copied into a file is a
/// liability, and copied material is exactly the kind of thing that should not outlive the session.
/// </summary>
internal sealed class SlotStore(int slotCount)
{
    private readonly ClipboardPayload?[] _slots = new ClipboardPayload?[slotCount];

    public int Count => _slots.Length;

    public ClipboardPayload? Get(int slot) => InRange(slot) ? _slots[slot] : null;

    public void Set(int slot, ClipboardPayload payload)
    {
        if (InRange(slot))
            _slots[slot] = payload;
    }

    public void Clear(int slot)
    {
        if (InRange(slot))
            _slots[slot] = null;
    }

    public void ClearAll() => Array.Clear(_slots);

    private bool InRange(int slot) => slot >= 0 && slot < _slots.Length;
}
