using System.Runtime.InteropServices;
using Frothedboard.Core;

namespace Frothedboard.App;

/// <summary>
/// A WH_KEYBOARD_LL hook. The callback arrives on the thread that installed it, and that thread
/// must keep pumping messages — so this is installed on the UI thread and the handler must stay
/// fast. Anything that can block (clipboard work) has to be queued, never done inline.
/// </summary>
internal sealed class KeyboardHook : IDisposable
{
    // Rooted in a field on purpose: if the GC collects the delegate, Windows calls into freed
    // memory and the process dies with no useful stack.
    private readonly Native.HookProc _callback;
    private readonly HashSet<int> _physicallyDown = [];

    private IntPtr _handle;

    public KeyboardHook() => _callback = OnKey;

    /// <summary>Return true to swallow the key so the foreground app never sees it.</summary>
    public Func<KeyEvent, bool>? Intercept { get; set; }

    public bool IsInstalled => _handle != IntPtr.Zero;

    public void Install()
    {
        if (IsInstalled)
            return;

        _handle = Native.SetWindowsHookExW(Native.WH_KEYBOARD_LL, _callback, Native.GetModuleHandleW(null), 0);
        if (_handle == IntPtr.Zero)
            throw new InvalidOperationException($"SetWindowsHookEx failed: {Marshal.GetLastWin32Error()}");
    }

    public void Uninstall()
    {
        if (!IsInstalled)
            return;

        Native.UnhookWindowsHookEx(_handle);
        _handle = IntPtr.Zero;
        _physicallyDown.Clear();
    }

    public void Dispose() => Uninstall();

    private IntPtr OnKey(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode < 0)
            return Native.CallNextHookEx(_handle, nCode, wParam, lParam);

        try
        {
            var data = Marshal.PtrToStructure<Native.KBDLLHOOKSTRUCT>(lParam);

            // Our own synthetic keystrokes must not re-enter the machine.
            if (data.dwExtraInfo == Native.InjectedTag)
                return Native.CallNextHookEx(_handle, nCode, wParam, lParam);

            int message = (int)wParam;
            bool isDown = message is Native.WM_KEYDOWN or Native.WM_SYSKEYDOWN;
            int vk = (int)data.vkCode;

            // KBDLLHOOKSTRUCT carries no repeat count, so infer it: a key-down for a key already
            // held is auto-repeat.
            bool isRepeat = isDown && !_physicallyDown.Add(vk);
            if (!isDown)
                _physicallyDown.Remove(vk);

            var e = new KeyEvent(vk, isDown, isRepeat, Environment.TickCount64);
            if (Intercept?.Invoke(e) == true)
                return 1;
        }
        catch
        {
            // An exception escaping into unmanaged code takes the whole process with it.
            // A dropped keystroke is survivable; a crashed keyboard hook is not.
        }

        return Native.CallNextHookEx(_handle, nCode, wParam, lParam);
    }
}
