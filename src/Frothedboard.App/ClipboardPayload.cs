using System.Runtime.InteropServices;

namespace Frothedboard.App;

/// <summary>
/// A snapshot of the clipboard across the formats that actually matter.
///
/// Deliberately a whitelist rather than "every format present": enumerating everything forces
/// delayed-rendering sources like Excel and Word to materialise each format on demand, which is
/// slow and occasionally hangs. These six cover text, rich text, web content, spreadsheet cells,
/// images and copied files.
/// </summary>
internal sealed class ClipboardPayload
{
    /// <summary>
    /// Explorer marks a file cut by putting DROPEFFECT_MOVE in this format alongside the file
    /// list. Without it a board built from Ctrl+X would paste as a copy and silently leave the
    /// originals behind, which looks like a move that half-happened.
    /// </summary>
    private const string PreferredDropEffect = "Preferred DropEffect";

    private static readonly string[] CapturedFormats =
    [
        DataFormats.UnicodeText,
        DataFormats.Html,
        DataFormats.Rtf,
        DataFormats.CommaSeparatedValue,
        DataFormats.FileDrop,
        DataFormats.Bitmap,
        PreferredDropEffect,
    ];

    private readonly Dictionary<string, object> _data;

    private ClipboardPayload(Dictionary<string, object> data, string? text)
    {
        _data = data;
        Text = text;
        Preview = BuildPreview(data, text);
    }

    public string? Text { get; }

    /// <summary>Short single-line description for the tray menu.</summary>
    public string Preview { get; }

    public static ClipboardPayload? Capture()
    {
        IDataObject? source;
        try
        {
            source = Clipboard.GetDataObject();
        }
        catch (ExternalException)
        {
            // Another process is holding the clipboard open. Nothing to do but skip this update.
            return null;
        }

        if (source is null)
            return null;

        var data = new Dictionary<string, object>();
        string? text = null;

        foreach (var format in CapturedFormats)
        {
            try
            {
                if (!source.GetDataPresent(format))
                    continue;

                if (source.GetData(format) is not { } value)
                    continue;

                // Stream-backed formats have to be drained now. A board gets pasted more than
                // once, and a MemoryStream handed out twice is empty the second time because the
                // first consumer left the position at the end.
                data[format] = value is Stream stream ? Drain(stream) : value;

                if (format == DataFormats.UnicodeText)
                    text = value as string;
            }
            catch
            {
                // One awkward format must not cost us the rest of the payload.
            }
        }

        return data.Count == 0 ? null : new ClipboardPayload(data, text);
    }

    public DataObject ToDataObject()
    {
        var obj = new DataObject();
        foreach (var (format, value) in _data)
        {
            try
            {
                // Every byte[] we hold came from a stream, so hand out a fresh one each time.
                obj.SetData(format, value is byte[] bytes ? new MemoryStream(bytes) : value);
            }
            catch
            {
                // Skip anything that refuses to go back on; the other formats still make it.
            }
        }

        return obj;
    }

    private static byte[] Drain(Stream stream)
    {
        if (stream.CanSeek)
            stream.Position = 0;

        using var buffer = new MemoryStream();
        stream.CopyTo(buffer);
        return buffer.ToArray();
    }

    /// <summary>True when this board came from a cut rather than a copy, so pasting it moves.</summary>
    public bool IsMove => IsMoveEffect(_data);

    private static bool IsMoveEffect(Dictionary<string, object> data) =>
        data.TryGetValue(PreferredDropEffect, out var effect)
        && effect is byte[] { Length: >= 4 } bytes
        && (BitConverter.ToUInt32(bytes) & 2) != 0;  // DROPEFFECT_MOVE

    private static string BuildPreview(Dictionary<string, object> data, string? text)
    {
        if (!string.IsNullOrWhiteSpace(text))
        {
            var flat = string.Join(' ', text.Split(['\r', '\n', '\t'], StringSplitOptions.RemoveEmptyEntries));
            return flat.Length <= 48 ? flat : string.Concat(flat.AsSpan(0, 47), "…");
        }

        if (data.TryGetValue(DataFormats.FileDrop, out var drop) && drop is string[] files)
        {
            var what = files.Length == 1 ? Path.GetFileName(files[0]) : $"{files.Length} files";
            return IsMoveEffect(data) ? $"{what}  (cut)" : what;
        }

        if (data.ContainsKey(DataFormats.Bitmap))
            return "(image)";

        return $"({data.Count} formats)";
    }
}
