namespace Frothedboard.Core;

/// <summary>Windows virtual-key codes, and the few classifications the chord machine needs.</summary>
public static class Vk
{
    public const int Shift = 0x10;
    public const int Control = 0x11;
    public const int Alt = 0x12;
    public const int LWin = 0x5B;
    public const int RWin = 0x5C;
    public const int LShift = 0xA0;
    public const int RShift = 0xA1;
    public const int LControl = 0xA2;
    public const int RControl = 0xA3;
    public const int LAlt = 0xA4;
    public const int RAlt = 0xA5;

    public const int C = 0x43;
    public const int V = 0x56;
    public const int X = 0x58;

    public const int D0 = 0x30;
    public const int D1 = 0x31;
    public const int D2 = 0x32;
    public const int D3 = 0x33;
    public const int D4 = 0x34;
    public const int D5 = 0x35;
    public const int D6 = 0x36;
    public const int D7 = 0x37;
    public const int D8 = 0x38;
    public const int D9 = 0x39;

    public const int NumPad0 = 0x60;
    public const int NumPad1 = 0x61;
    public const int NumPad2 = 0x62;
    public const int NumPad3 = 0x63;
    public const int NumPad4 = 0x64;
    public const int NumPad5 = 0x65;
    public const int NumPad6 = 0x66;
    public const int NumPad7 = 0x67;
    public const int NumPad8 = 0x68;
    public const int NumPad9 = 0x69;

    public static bool IsControl(int vk) => vk is Control or LControl or RControl;
    public static bool IsShift(int vk) => vk is Shift or LShift or RShift;
    public static bool IsAlt(int vk) => vk is Alt or LAlt or RAlt;
    public static bool IsWin(int vk) => vk is LWin or RWin;
    public static bool IsModifier(int vk) => IsControl(vk) || IsShift(vk) || IsAlt(vk) || IsWin(vk);

    /// <summary>
    /// Maps a top-row or numpad digit key to a slot index 0-9. Returns -1 for anything else.
    /// Both digit rows are accepted so the chord works with or without a numpad.
    /// </summary>
    public static int ToSlot(int vk) => vk switch
    {
        >= D0 and <= D9 => vk - D0,
        >= NumPad0 and <= NumPad9 => vk - NumPad0,
        _ => -1,
    };
}
