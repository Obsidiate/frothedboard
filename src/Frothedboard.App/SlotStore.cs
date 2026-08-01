using System.Text.Json;

namespace Frothedboard.App;

/// <summary>
/// The ten frothed boards. The system clipboard is the eleventh and is not stored here — it stays
/// where Windows keeps it, untouched.
/// </summary>
internal sealed class SlotStore(int slotCount, string? persistPath = null)
{
    private readonly ClipboardPayload?[] _slots = new ClipboardPayload?[slotCount];
    private readonly string _path = persistPath ?? DefaultPath;

    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "frothedboard",
        "boards.json");

    public int Count => _slots.Length;

    public ClipboardPayload? Get(int slot) => InRange(slot) ? _slots[slot] : null;

    public void Set(int slot, ClipboardPayload payload)
    {
        if (!InRange(slot))
            return;

        _slots[slot] = payload;
        Save();
    }

    public void Clear(int slot)
    {
        if (!InRange(slot))
            return;

        _slots[slot] = null;
        Save();
    }

    public void ClearAll()
    {
        Array.Clear(_slots);
        Save();
    }

    /// <summary>
    /// Only text survives a restart. Images and copied file lists are held in memory for the
    /// session and deliberately not written to disk — persisting them means writing whatever you
    /// happened to copy into a file on disk, and the surprise is not worth the convenience.
    /// </summary>
    public void Save()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            var text = _slots.Select(s => s?.Text).ToArray();
            File.WriteAllText(_path, JsonSerializer.Serialize(text));
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    public void Load()
    {
        try
        {
            if (!File.Exists(_path))
                return;

            var text = JsonSerializer.Deserialize<string?[]>(File.ReadAllText(_path));
            if (text is null)
                return;

            for (int i = 0; i < Math.Min(text.Length, _slots.Length); i++)
                if (!string.IsNullOrEmpty(text[i]))
                    _slots[i] = ClipboardPayload.FromText(text[i]!);
        }
        catch (Exception e) when (e is IOException or JsonException or UnauthorizedAccessException)
        {
        }
    }

    private bool InRange(int slot) => slot >= 0 && slot < _slots.Length;
}
