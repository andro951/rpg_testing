namespace Csc592.IntentParser;

/// <summary>Limits and wire-format options shared by all native ports.</summary>
public sealed record IntentOptions(
    bool JsonPatch = false,
    string IdKey = "id",
    int MaxChars = 65536,
    int MaxDepth = 64,
    int MaxOperations = 256,
    int MaxBoundaryAttempts = 4096,
    string? PathSyntax = null,
    string? OutputFormat = null);
