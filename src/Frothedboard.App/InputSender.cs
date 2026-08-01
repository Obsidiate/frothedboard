using Frothedboard.Core;

namespace Frothedboard.App;

internal static class InputSender
{
    /// <summary>
    /// Sends a complete Ctrl+V, including both Ctrl transitions, whatever the physical keyboard is
    /// doing. Sending only V and relying on the user's real Ctrl being down is tempting but loses
    /// the race whenever they let go a few milliseconds early.
    /// </summary>
    public static void SendCtrlV() =>
        Send(
            Key(Vk.LControl, down: true),
            Key(Vk.V, down: true),
            Key(Vk.V, down: false),
            Key(Vk.LControl, down: false));

    private static Native.INPUT Key(int vk, bool down) => new()
    {
        type = Native.INPUT_KEYBOARD,
        u = new Native.INPUTUNION
        {
            ki = new Native.KEYBDINPUT
            {
                wVk = (ushort)vk,
                wScan = 0,
                dwFlags = down ? 0 : Native.KEYEVENTF_KEYUP,
                time = 0,
                dwExtraInfo = Native.InjectedTag,
            },
        },
    };

    private static void Send(params Native.INPUT[] inputs) =>
        Native.SendInput((uint)inputs.Length, inputs, System.Runtime.InteropServices.Marshal.SizeOf<Native.INPUT>());
}
