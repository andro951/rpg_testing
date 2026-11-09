using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
namespace Csc592.IntentParser;
public static partial class IntentParser
{
    private static bool DeepStateEquals(JsonNode? a, JsonNode? b)
    {
        if (a is JsonObject ao && b is JsonObject bo) return ao.Count == bo.Count && ao.All(p => bo.ContainsKey(p.Key) && DeepStateEquals(p.Value, bo[p.Key]));
        if (a is JsonArray aa && b is JsonArray ba) return aa.Count == ba.Count && aa.Select((v, i) => DeepStateEquals(v, ba[i])).All(x => x);
        if (a is JsonObject or JsonArray || b is JsonObject or JsonArray) return false;
        return JsonContract.TypedEquals(a, b);
    }
    public static JsonObject ReplayPrepared(JsonArray records, IntentOptions? options = null)
    {
        options ??= new(); var results = new JsonArray(); int accepted = 0;
        for (int index = 0; index < records.Count; index++)
        {
            if (records[index] is not JsonObject record) throw new ArgumentException($"Record {index} lacks textual output");
            var output = record["output"] ?? record["text"];
            if (output?.GetValueKind() != System.Text.Json.JsonValueKind.String) throw new ArgumentException($"Record {index} lacks textual output");
            string raw = output.GetValue<string>();
            var result = new JsonObject { ["index"] = index, ["name"] = JsonContract.Clone(record["name"]), ["rawOutput"] = raw, ["rawSha256"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(raw))).ToLowerInvariant() };
            try
            {
                if (!record.ContainsKey("input")) throw new ArgumentException("Non-JSON value");
                var patch = NormalizeIntent(raw, record["input"], options);
                var canonical = options.JsonPatch ? NormalizeIntent(raw, record["input"], options with { JsonPatch = false }) : patch;
                var final = ApplyPatch(record["input"], canonical, options);
                result["accepted"] = true; result["patch"] = patch; result["finalState"] = final;
                if (record.ContainsKey("expected")) result["expectedStateMatches"] = DeepStateEquals(final, record["expected"]);
                if (record.ContainsKey("reject")) result["expectedRejectionMatches"] = record["reject"]?.GetValueKind() == System.Text.Json.JsonValueKind.False;
                accepted++;
            }
            catch (Exception ex)
            {
                result["accepted"] = false; result["error"] = ex.Message;
                if (record.ContainsKey("expected")) result["expectedStateMatches"] = false;
                if (record.ContainsKey("reject")) result["expectedRejectionMatches"] = record["reject"]?.GetValueKind() == System.Text.Json.JsonValueKind.True;
            }
            results.Add(result);
        }
        return new JsonObject { ["mode"] = "offline-prepared-output-replay", ["liveInference"] = false, ["format"] = options.JsonPatch ? "rfc6902" : "custom", ["total"] = results.Count, ["accepted"] = accepted, ["rejected"] = results.Count - accepted, ["results"] = results };
    }
}
