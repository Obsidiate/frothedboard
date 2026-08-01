namespace Frothedboard.App;

/// <summary>
/// An invisible window that exists for two reasons: it gives the clipboard listener an HWND to
/// deliver WM_CLIPBOARDUPDATE to, and it gives the keyboard hook somewhere to hand slow clipboard
/// work off to so that work runs after the hook has returned rather than inside it.
///
/// A Form rather than a bare Control: a parentless Control is created with WS_CHILD and no parent
/// HWND, which fails outright.
/// </summary>
internal sealed class MessageWindow : Form
{
    public MessageWindow()
    {
        ShowInTaskbar = false;
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        Location = new Point(-32000, -32000);
        Size = new Size(1, 1);

        // Touching Handle forces the window into existence; the listener needs it now, not lazily.
        Native.AddClipboardFormatListener(Handle);
    }

    public event Action? ClipboardChanged;

    /// <summary>Never becomes visible, whatever anyone asks.</summary>
    protected override void SetVisibleCore(bool value) => base.SetVisibleCore(false);

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == Native.WM_CLIPBOARDUPDATE)
            ClipboardChanged?.Invoke();

        base.WndProc(ref m);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing && IsHandleCreated)
            Native.RemoveClipboardFormatListener(Handle);

        base.Dispose(disposing);
    }
}
