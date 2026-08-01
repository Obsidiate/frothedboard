namespace Frothedboard.Core.Tests;

/// <summary>
/// The promise this whole project rests on: if you never touch a digit, Ctrl+C and Ctrl+V
/// behave exactly as they always have. These are the tests that hold that promise honest.
/// </summary>
public class OrdinaryCopyPasteIsUntouched
{
    [Fact]
    public void PlainCtrlC_ReachesTheApp()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.C).Up(Vk.LControl);

        Assert.True(d.WasPassed(Vk.C));
        Assert.Equal(0, d.Count(EffectKind.CaptureToSlot));
        Assert.Equal(ChordStateMachine.State.Idle, d.State);
    }

    [Fact]
    public void PlainCtrlV_PastesOnceWhenCtrlComesUp()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.V).Up(Vk.LControl);

        // V is swallowed on the way down — you cannot un-paste — and repaid on Ctrl release.
        Assert.True(d.WasSwallowed(Vk.V));
        Assert.Equal(1, d.Count(EffectKind.SendNativePaste));
        Assert.Equal(0, d.Count(EffectKind.PasteFromSlot));
    }

    [Fact]
    public void SwallowedKeyUp_IsSwallowedToo_SoNoAppSeesAStrayRelease()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.V).Up(Vk.LControl);

        Assert.True(d.WasSwallowed(Vk.V, down: false));
    }

    [Fact]
    public void OrdinaryTyping_IsNeverTouched()
    {
        var d = new Driver().Tap('A').Tap('B').Tap(Vk.D3).Tap(Vk.V).Tap(Vk.C);

        Assert.Empty(d.Effects);
        Assert.Empty(d.Swallowed);
    }

    [Theory]
    [InlineData(Vk.LShift)]
    [InlineData(Vk.LAlt)]
    [InlineData(Vk.LWin)]
    public void CtrlPlusAnotherModifier_NeverEngages(int otherModifier)
    {
        // Ctrl+Shift+V is "paste without formatting" in half the world's apps. Leave it alone.
        var d = new Driver().Down(Vk.LControl).Down(otherModifier).Tap(Vk.V).Tap(Vk.C);

        Assert.Empty(d.Effects);
        Assert.Empty(d.Swallowed);
    }

    [Fact]
    public void CtrlPlusDigit_WithNoChord_ReachesTheApp()
    {
        // Ctrl+3 is "switch to tab 3". Swallowing it would be a daily papercut.
        var d = new Driver().Down(Vk.LControl).Tap(Vk.D3).Up(Vk.LControl);

        Assert.True(d.WasPassed(Vk.D3));
        Assert.Empty(d.Effects);
    }
}

public class CopyChord
{
    [Fact]
    public void CtrlC_ThenDigit_CapturesToThatSlot()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.C).Tap(Vk.D3).Up(Vk.LControl);

        // The real copy still happened — C was never swallowed.
        Assert.True(d.WasPassed(Vk.C));
        Assert.True(d.WasSwallowed(Vk.D3));
        Assert.Equal([EffectKind.ArmCopyCapture, EffectKind.CaptureToSlot], d.Kinds);
        Assert.Equal(3, d.SlotOf(EffectKind.CaptureToSlot));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(5)]
    [InlineData(9)]
    public void EveryDigit_WorksOnBothDigitRows(int slot)
    {
        var topRow = new Driver().Down(Vk.LControl).Tap(Vk.C).Tap(Vk.D0 + slot).Up(Vk.LControl);
        var numpad = new Driver().Down(Vk.LControl).Tap(Vk.C).Tap(Vk.NumPad0 + slot).Up(Vk.LControl);

        Assert.Equal(slot, topRow.SlotOf(EffectKind.CaptureToSlot));
        Assert.Equal(slot, numpad.SlotOf(EffectKind.CaptureToSlot));
    }

    [Fact]
    public void CtrlC_ThenCtrlReleased_AbandonsTheChord()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.C).Up(Vk.LControl).Tap(Vk.D3);

        Assert.Equal([EffectKind.ArmCopyCapture, EffectKind.CancelCopyCapture], d.Kinds);
        Assert.True(d.WasPassed(Vk.D3));
    }

    [Fact]
    public void CtrlC_ThenSomeOtherKey_AbandonsTheChord_AndTheKeyStillGetsThrough()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.C).Tap('S');

        Assert.Equal([EffectKind.ArmCopyCapture, EffectKind.CancelCopyCapture], d.Kinds);
        Assert.True(d.WasPassed('S'));
    }

    [Fact]
    public void CopyChord_ExpiresAfterItsTimeout()
    {
        var config = new FrothedConfig { CopyChordTimeoutMs = 1500 };
        var d = new Driver(config).Down(Vk.LControl).Tap(Vk.C).Advance(2000).Tap(Vk.D3);

        // Too late to be part of the chord, so the digit is an ordinary Ctrl+3 again.
        Assert.Equal(0, d.Count(EffectKind.CaptureToSlot));
        Assert.True(d.WasPassed(Vk.D3));
    }

    [Fact]
    public void CtrlX_TakesTheChordToo()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.X).Tap(Vk.D7).Up(Vk.LControl);

        Assert.True(d.WasPassed(Vk.X));
        Assert.Equal(7, d.SlotOf(EffectKind.CaptureToSlot));
    }

    [Fact]
    public void CtrlX_CanBeTurnedOff()
    {
        var d = new Driver(new FrothedConfig { EnableCut = false })
            .Down(Vk.LControl).Tap(Vk.X).Tap(Vk.D7).Up(Vk.LControl);

        Assert.Empty(d.Effects);
    }
}

public class PasteChord
{
    [Fact]
    public void CtrlV_ThenDigit_PastesThatSlot_AndNeverAlsoPastesNormally()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.V).Tap(Vk.D4).Up(Vk.LControl);

        Assert.Equal([EffectKind.PasteFromSlot], d.Kinds);
        Assert.Equal(4, d.SlotOf(EffectKind.PasteFromSlot));
        Assert.True(d.WasSwallowed(Vk.V));
        Assert.True(d.WasSwallowed(Vk.D4));
    }

    [Fact]
    public void HeldCtrlPasteBurst_YieldsOnePastePerPress_InOrder()
    {
        var d = new Driver().Down(Vk.LControl).Tap(Vk.V).Tap(Vk.V).Tap(Vk.V).Up(Vk.LControl);

        Assert.Equal(3, d.Count(EffectKind.SendNativePaste));
    }

    [Fact]
    public void AutoRepeatingPaste_YieldsOnePastePerRepeat()
    {
        var d = new Driver()
            .Down(Vk.LControl)
            .Down(Vk.V)
            .Down(Vk.V, repeat: true)
            .Down(Vk.V, repeat: true)
            .Up(Vk.V)
            .Up(Vk.LControl);

        Assert.Equal(3, d.Count(EffectKind.SendNativePaste));
    }

    [Fact]
    public void CtrlV_ThenAnotherShortcut_PastesFirst_ThenLetsTheShortcutThrough()
    {
        // Ctrl+V Ctrl+S without letting go of Ctrl must save the paste, not lose it.
        var d = new Driver().Down(Vk.LControl).Tap(Vk.V).Tap('S');

        Assert.Equal([EffectKind.SendNativePaste], d.Kinds);
        Assert.True(d.WasPassed('S'));
    }

    [Fact]
    public void Backstop_PastesExactlyOnce_AndALaterDigitDoesNotPasteAgain()
    {
        // The reason the backstop is 2s and not 300ms: a short timer would fire the ordinary
        // paste, and then a hesitant user tapping a digit would get a second, unwanted paste.
        var d = new Driver(new FrothedConfig { PasteBackstopMs = 2000 })
            .Down(Vk.LControl).Down(Vk.V).Advance(2500).Tick().Tap(Vk.D3).Up(Vk.LControl);

        Assert.Equal(1, d.Count(EffectKind.SendNativePaste));
        Assert.Equal(0, d.Count(EffectKind.PasteFromSlot));
        Assert.True(d.WasPassed(Vk.D3));
    }

    [Fact]
    public void SlotsBeyondTheConfiguredCount_AreNotChordDigits()
    {
        var d = new Driver(new FrothedConfig { SlotCount = 5 })
            .Down(Vk.LControl).Tap(Vk.V).Tap(Vk.D7).Up(Vk.LControl);

        Assert.Equal(0, d.Count(EffectKind.PasteFromSlot));
        Assert.Equal(1, d.Count(EffectKind.SendNativePaste));
    }
}

public class ModifierBookkeeping
{
    [Fact]
    public void RightCtrl_WorksExactlyLikeLeftCtrl()
    {
        var d = new Driver().Down(Vk.RControl).Tap(Vk.C).Tap(Vk.D2).Up(Vk.RControl);

        Assert.Equal(2, d.SlotOf(EffectKind.CaptureToSlot));
    }

    [Fact]
    public void WithBothCtrlsDown_TheChordSurvivesReleasingOnlyOne()
    {
        var d = new Driver()
            .Down(Vk.LControl).Down(Vk.RControl).Tap(Vk.V)
            .Up(Vk.LControl);

        Assert.Equal(0, d.Count(EffectKind.SendNativePaste));

        d.Up(Vk.RControl);
        Assert.Equal(1, d.Count(EffectKind.SendNativePaste));
    }

    [Fact]
    public void CopyChordThenPasteChord_WithoutEverReleasingCtrl()
    {
        var d = new Driver()
            .Down(Vk.LControl)
            .Tap(Vk.C).Tap(Vk.D1)
            .Tap(Vk.V).Tap(Vk.D2)
            .Up(Vk.LControl);

        Assert.Equal(
            [EffectKind.ArmCopyCapture, EffectKind.CaptureToSlot, EffectKind.PasteFromSlot],
            d.Kinds);
        Assert.Equal(1, d.SlotOf(EffectKind.CaptureToSlot));
        Assert.Equal(2, d.SlotOf(EffectKind.PasteFromSlot));
    }

    [Fact]
    public void Reset_RepaysAPasteItStillOwes_RatherThanSwallowingIt()
    {
        var d = new Driver().Down(Vk.LControl).Down(Vk.V).Reset();

        Assert.Equal(1, d.Count(EffectKind.SendNativePaste));
        Assert.Equal(ChordStateMachine.State.Idle, d.State);
    }

    [Fact]
    public void TickWhileIdle_DoesNothing()
    {
        var d = new Driver().Advance(60_000).Tick().Tick();

        Assert.Empty(d.Effects);
    }
}
