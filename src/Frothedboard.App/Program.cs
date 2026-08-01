namespace Frothedboard.App;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        // One hook is enough; a second instance would double every paste.
        using var single = new Mutex(initiallyOwned: true, "frothedboard.singleinstance", out bool isFirst);
        if (!isFirst)
            return;

        ApplicationConfiguration.Initialize();
        Application.Run(new FrothedContext());
    }
}
