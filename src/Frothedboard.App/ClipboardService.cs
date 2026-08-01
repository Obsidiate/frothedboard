using System.Runtime.InteropServices;
using Frothedboard.Core;

namespace Frothedboard.App;

/// <summary>
/// All clipboard access, on the UI thread. Every method here can block for tens of milliseconds
/// when another process is holding the clipboard, so none of it may run inside the keyboard hook.
/// The waits are awaited rather than slept so the message pump keeps running and
/// WM_CLIPBOARDUPDATE can still arrive while we wait for it.
/// </summary>
internal sealed class ClipboardService(FrothedConfig config, SlotStore slots)
{
    private ClipboardPayload? _mirror;
    private ClipboardPayload? _armed;
    private uint _armedSequence;

    public event Action<string>? Notice;

    /// <summary>
    /// Keeps a live copy of the clipboard. This is what makes a slotted copy free: by the time we
    /// learn the user wanted slot 3, the payload they are about to overwrite is already in hand,
    /// so Ctrl+C itself never has to stop and read anything.
    /// </summary>
    public void OnClipboardChanged() => _mirror = ClipboardPayload.Capture() ?? _mirror;

    public void Arm()
    {
        _armed = _mirror;
        _armedSequence = Native.GetClipboardSequenceNumber();
    }

    public void CancelArm() => _armed = null;

    public async Task CaptureToSlotAsync(int slot)
    {
        var armed = _armed;
        _armed = null;

        // The digit can beat the app's copy onto the clipboard, so wait for the payload to land.
        long deadline = Environment.TickCount64 + config.ClipboardSettleTimeoutMs;
        while (Native.GetClipboardSequenceNumber() == _armedSequence && Environment.TickCount64 < deadline)
            await Task.Delay(15);

        if (Native.GetClipboardSequenceNumber() == _armedSequence)
        {
            // The copy produced nothing — most likely nothing was selected. Change nothing.
            Notice?.Invoke($"Board {slot}: nothing was copied");
            return;
        }

        var copied = ClipboardPayload.Capture();
        if (copied is null)
        {
            Notice?.Invoke($"Board {slot}: could not read the clipboard");
            return;
        }

        slots.Set(slot, copied);

        // Put back whatever was on the clipboard beforehand. This is what keeps the boards
        // registers rather than history: a slotted copy leaves an ordinary Ctrl+V alone.
        if (armed is not null)
            Write(armed);

        Notice?.Invoke($"Board {slot} ← {copied.Preview}");
    }

    public async Task PasteSlotAsync(int slot)
    {
        if (slots.Get(slot) is not { } payload)
        {
            Notice?.Invoke($"Board {slot} is empty");
            return;
        }

        var restore = _mirror;

        Write(payload);
        await Task.Delay(20);

        InputSender.SendCtrlV();

        // Give the target app time to actually read the clipboard before taking it back.
        // Restoring too eagerly is the most likely cause of a paste arriving empty.
        await Task.Delay(config.PasteRestoreDelayMs);

        if (restore is not null)
            Write(restore);
    }

    private void Write(ClipboardPayload payload)
    {
        try
        {
            Clipboard.SetDataObject(payload.ToDataObject(), copy: true, retryTimes: 10, retryDelay: 30);
        }
        catch (ExternalException)
        {
            Notice?.Invoke("The clipboard was locked by another app");
        }
    }
}
