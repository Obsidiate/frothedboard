namespace Frothedboard.App;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        MessageBox.Show("frothedboard toolchain proof");
    }
}
