using Microsoft.Win32;
using Frothedboard.Core;

namespace Frothedboard.App;

/// <summary>Wires the hook, the state machine and the clipboard together, and owns the tray icon.</summary>
internal sealed class FrothedContext : ApplicationContext
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string RunValue = "frothedboard";

    private readonly FrothedConfig _config = new();
    private readonly ChordStateMachine _machine;
    private readonly KeyboardHook _hook = new();
    private readonly SlotStore _slots;
    private readonly ClipboardService _clipboard;
    private readonly MessageWindow _window = new();
    private readonly NotifyIcon _tray;
    private readonly System.Windows.Forms.Timer _timer;

    private bool _paused;

    public FrothedContext()
    {
        _machine = new ChordStateMachine(_config);
        _slots = new SlotStore(_config.SlotCount);
        _clipboard = new ClipboardService(_config, _slots);

        _window.ClipboardChanged += _clipboard.OnClipboardChanged;
        _clipboard.OnClipboardChanged();

        _tray = new NotifyIcon
        {
            Icon = LoadTrayIcon(),
            Text = "frothedboard",
            Visible = true,
            ContextMenuStrip = new ContextMenuStrip(),
        };
        _tray.ContextMenuStrip.Opening += (_, _) => BuildMenu();

        // The chord normally closes itself on the next keystroke or on the Ctrl release. This is
        // only here for a Ctrl key left physically stuck down, or a key-up lost to a focus change.
        _timer = new System.Windows.Forms.Timer { Interval = 500 };
        _timer.Tick += (_, _) => Run(_machine.Tick(Environment.TickCount64).Effects);
        _timer.Start();

        _hook.Intercept = OnKey;
        _hook.Install();
    }

    private bool OnKey(KeyEvent e)
    {
        if (_paused)
            return false;

        var result = _machine.Process(e);
        Run(result.Effects);
        return result.Suppress;
    }

    private void Run(IReadOnlyList<Effect> effects)
    {
        foreach (var effect in effects)
        {
            switch (effect.Kind)
            {
                case EffectKind.ArmCopyCapture:
                    _clipboard.Arm();
                    break;

                case EffectKind.CancelCopyCapture:
                    _clipboard.CancelArm();
                    break;

                case EffectKind.SendNativePaste:
                    // Synchronous on purpose. This has to be queued into the input stream before
                    // the keystroke that triggered the flush reaches the app, or Ctrl+V Ctrl+S
                    // saves the document before it pastes into it.
                    InputSender.SendCtrlV();
                    break;

                case EffectKind.CaptureToSlot:
                    Defer(() => _clipboard.CaptureToSlotAsync(effect.Slot));
                    break;

                case EffectKind.PasteFromSlot:
                    Defer(() => _clipboard.PasteSlotAsync(effect.Slot));
                    break;
            }
        }
    }

    /// <summary>Runs clipboard work after the hook has returned, never inside it.</summary>
    private void Defer(Func<Task> work) => _window.BeginInvoke(async () =>
    {
        try
        {
            await work();
        }
        catch
        {
            // A failed clipboard round-trip must not take the hook down with it.
        }
    });

    private void BuildMenu()
    {
        var menu = _tray.ContextMenuStrip!;
        menu.Items.Clear();

        for (int i = 0; i < _slots.Count; i++)
        {
            int slot = i;
            var payload = _slots.Get(slot);
            var item = new ToolStripMenuItem($"Board {slot}   {payload?.Preview ?? "—"}")
            {
                Enabled = payload is not null,
            };
            item.Click += (_, _) => Defer(() => _clipboard.PasteSlotAsync(slot));
            menu.Items.Add(item);
        }

        menu.Items.Add(new ToolStripSeparator());

        var pause = new ToolStripMenuItem("Paused", null, (_, _) => _paused = !_paused) { Checked = _paused };
        menu.Items.Add(pause);

        var startup = new ToolStripMenuItem("Start with Windows", null, (_, _) => ToggleStartup())
        {
            Checked = IsStartupEnabled(),
        };
        menu.Items.Add(startup);

        menu.Items.Add(new ToolStripMenuItem("Clear all boards", null, (_, _) => _slots.ClearAll()));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(new ToolStripMenuItem("Quit", null, (_, _) => ExitThread()));
    }

    /// <summary>
    /// Pulls the icon out of the embedded .ico and asks for the exact size the tray wants, so
    /// Windows picks the hand-drawn 16x16 rather than squashing the 256x256 down to it.
    /// </summary>
    private static Icon LoadTrayIcon()
    {
        using var stream = typeof(FrothedContext).Assembly.GetManifestResourceStream("frothedboard.ico");
        return stream is null ? SystemIcons.Application : new Icon(stream, SystemInformation.SmallIconSize);
    }

    private static bool IsStartupEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey);
        return key?.GetValue(RunValue) is not null;
    }

    private static void ToggleStartup()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey, writable: true);
        if (key is null)
            return;

        if (key.GetValue(RunValue) is not null)
            key.DeleteValue(RunValue, throwOnMissingValue: false);
        else
            key.SetValue(RunValue, $"\"{Environment.ProcessPath}\"");
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _hook.Dispose();
            _timer.Dispose();

            // Never exit leaving a board's contents sitting on the system clipboard, which is what
            // happens if we are quit mid-paste between writing a board and putting the real
            // clipboard back.
            _clipboard.RestoreSystemClipboard();
            _slots.ClearAll();

            _tray.Visible = false;
            _tray.Dispose();
            _window.Dispose();
        }

        base.Dispose(disposing);
    }
}
