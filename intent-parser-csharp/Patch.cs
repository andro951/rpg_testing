using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Encodings.Web;
using System.Text.RegularExpressions;

namespace Csc592.IntentParser;

public static class JsonContract
{
    private static void AssertUnicode(string text)
    {
        for (int i = 0; i < text.Length; i++)
        {
            if (char.IsHighSurrogate(text[i]))
            {
                if (i + 1 >= text.Length || !char.IsLowSurrogate(text[i + 1])) throw new ArgumentException("Unpaired UTF-16 surrogate");
                i++;
            }
            else if (char.IsLowSurrogate(text[i])) throw new ArgumentException("Unpaired UTF-16 surrogate");
        }
    }
    public static void AssertJson(JsonNode? node)
    {
        if (node is JsonObject obj) { foreach (var p in obj) { AssertUnicode(p.Key); AssertJson(p.Value); } return; }
        if (node is JsonArray arr) { foreach (var v in arr) AssertJson(v); return; }
        if (node is null) return;
        var kind = node.GetValueKind();
        if (kind == JsonValueKind.String) { AssertUnicode(node.GetValue<string>()); return; }
        if (kind == JsonValueKind.Number)
        {
            double value;
            try { value = double.Parse(node.ToJsonString(), CultureInfo.InvariantCulture); }
            catch { throw new ArgumentException("Nonfinite or unsafe JSON number"); }
            if (value == 0 && node.ToJsonString().Split('e', 'E')[0].Any(c => c >= '1' && c <= '9'))
                throw new ArgumentException("JSON number underflow");
            if (!double.IsFinite(value) || (Math.Truncate(value) == value && Math.Abs(value) > 9007199254740991d))
                throw new ArgumentException("Nonfinite or unsafe JSON number");
        }
        else if (kind is not (JsonValueKind.String or JsonValueKind.True or JsonValueKind.False or JsonValueKind.Null)) throw new ArgumentException("Non-JSON value");
    }
    public static JsonNode? Clone(JsonNode? node) { AssertJson(node); return node is null ? null : JsonNode.Parse(Stringify(node), documentOptions: new JsonDocumentOptions { MaxDepth = int.MaxValue }); }
    public static bool TypedEquals(JsonNode? a, JsonNode? b) => Stringify(a) == Stringify(b);
    private static string Quote(string value)
    {
        var result = new System.Text.StringBuilder("\"");
        for (int i = 0; i < value.Length; i++)
        {
            char c = value[i];
            switch (c)
            {
                case '"': result.Append("\\\""); break;
                case '\\': result.Append("\\\\"); break;
                case '\b': result.Append("\\b"); break;
                case '\f': result.Append("\\f"); break;
                case '\n': result.Append("\\n"); break;
                case '\r': result.Append("\\r"); break;
                case '\t': result.Append("\\t"); break;
                default:
                    if (c < 0x20 || (char.IsSurrogate(c) && !(char.IsHighSurrogate(c) && i + 1 < value.Length && char.IsLowSurrogate(value[i + 1])) && !(char.IsLowSurrogate(c) && i > 0 && char.IsHighSurrogate(value[i - 1]))))
                        result.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                    else result.Append(c);
                    break;
            }
        }
        return result.Append('"').ToString();
    }
    public static string Stringify(JsonNode? node)
    {
        AssertJson(node);
        if (node is null) return "null";
        if (node is JsonArray arr) return "[" + string.Join(",", arr.Select(Stringify)) + "]";
        if (node is JsonObject obj)
        {
            static uint? Index(string s) => uint.TryParse(s, NumberStyles.None, CultureInfo.InvariantCulture, out var n) && n != uint.MaxValue && n.ToString(CultureInfo.InvariantCulture) == s ? n : null;
            var props = obj.OrderBy(p => Index(p.Key).HasValue ? 0 : 1).ThenBy(p => Index(p.Key) ?? 0);
            return "{" + string.Join(",", props.Select(p => Quote(p.Key) + ":" + Stringify(p.Value))) + "}";
        }
        if (node.GetValueKind() == JsonValueKind.Number)
        {
            var d = double.Parse(node.ToJsonString(), CultureInfo.InvariantCulture);
            if (d == 0) return "0";
            var s = d.ToString("R", CultureInfo.InvariantCulture).ToLowerInvariant();
            if (s.Contains('e'))
            {
                var parts = s.Split('e'); int exponent = int.Parse(parts[1], CultureInfo.InvariantCulture);
                if (Math.Abs(d) >= 1e-6 && Math.Abs(d) < 1e21)
                {
                    bool negative = parts[0].StartsWith('-'); var mantissa = parts[0].TrimStart('-'); int point = mantissa.IndexOf('.'); if (point < 0) point = mantissa.Length;
                    var digits = mantissa.Replace(".", ""); int position = point + exponent;
                    s = position <= 0 ? "0." + new string('0', -position) + digits : position >= digits.Length ? digits + new string('0', position - digits.Length) : digits.Insert(position, ".");
                    return negative ? "-" + s : s;
                }
                return parts[0] + "e" + (exponent >= 0 ? "+" : "-") + Math.Abs(exponent).ToString(CultureInfo.InvariantCulture);
            }
            return s;
        }
        return node.GetValueKind() == JsonValueKind.String ? Quote(node.GetValue<string>()) : node.ToJsonString();
    }
}

public static partial class IntentParser
{
    private sealed record Resolution(JsonNode? Node, JsonNode? Parent, string? Key, List<string> Pointer);
    private static bool Scalar(JsonNode? n) => n is not JsonArray && n is not JsonObject;
    private static string PropertyKey(JsonNode? n) => n?.GetValueKind() == JsonValueKind.String ? n.GetValue<string>() : JsonContract.Stringify(n);
    private static JsonArray Path(JsonObject op, string field) => op[field] as JsonArray ?? throw new ArgumentException("Path must contain scalar JSON tokens");
    private static Resolution Resolve(JsonNode? root, JsonArray path, IntentOptions options)
    {
        JsonNode? node = root, parent = null; string? key = null; var pointer = new List<string>();
        foreach (var segment in path)
        {
            parent = node;
            if (node is JsonArray arr)
            {
                var matches = new List<int>();
                for (int i = 0; i < arr.Count; i++)
                {
                    var v = arr[i];
                    bool match = v is JsonObject obj ? obj.ContainsKey(options.IdKey) && JsonContract.TypedEquals(obj[options.IdKey], segment) : v is JsonArray ? false : JsonContract.TypedEquals(v, segment);
                    if (match) matches.Add(i);
                }
                if (matches.Count != 1) throw new ArgumentException("Array ID must resolve exactly once: " + PropertyKey(segment));
                key = matches[0].ToString(CultureInfo.InvariantCulture); node = arr[matches[0]];
            }
            else if (node is JsonObject obj && obj.TryGetPropertyValue(PropertyKey(segment), out var next)) { key = PropertyKey(segment); node = next; }
            else throw new ArgumentException("Missing path segment: " + PropertyKey(segment));
            pointer.Add(key);
        }
        return new(node, parent, key, pointer);
    }
    private static string Pointer(List<string> parts) => parts.Count == 0 ? "" : "/" + string.Join("/", parts.Select(s => s.Replace("~", "~0").Replace("/", "~1")));
    private static void Delete(Resolution r)
    {
        if (r.Parent is JsonArray arr) arr.RemoveAt(int.Parse(r.Key!, CultureInfo.InvariantCulture));
        else if (r.Parent is JsonObject obj) obj.Remove(r.Key!);
        else throw new ArgumentException("Root removal unsupported");
    }
    private static bool TryIdentity(JsonNode? value, string idKey, out JsonNode? identity)
    {
        if (value is JsonObject obj) return obj.TryGetPropertyValue(idKey, out identity);
        identity = value;
        return value is not JsonArray;
    }
    private static bool HasIdentityCollision(IEnumerable<JsonNode?> values, JsonNode? value, string idKey)
    {
        if (!TryIdentity(value, idKey, out var identity)) return false;
        if (!Scalar(identity)) throw new ArgumentException("Object identities must be scalar JSON values");
        return values.Any(other => TryIdentity(other, idKey, out var otherIdentity) && JsonContract.TypedEquals(identity, otherIdentity));
    }
    private static void CheckAppend(JsonArray array, JsonNode? value, string idKey)
    {
        if (HasIdentityCollision(array, value, idKey)) throw new ArgumentException("Append would create ambiguous duplicate identity");
    }
    private static void ValidateShape(JsonNode? raw)
    {
        if (raw is not JsonObject op || op["op"]?.GetValueKind() != JsonValueKind.String) throw new ArgumentException("Invalid operation");
        string name = op["op"]!.GetValue<string>();
        if (!new[] { "append", "update", "remove", "copy", "move" }.Contains(name)) throw new ArgumentException("Invalid operation");
        bool two = name is "copy" or "move";
        string[] allowed = two ? ["op", "from", "to", "unlabeledPaths"] : name == "remove" ? ["op", "path"] : ["op", "path", "value", "unlabeledPathValue"];
        if(op.ContainsKey("semantic"))
        {
            if(name!="append" || op["semantic"]?.GetValueKind()!=JsonValueKind.String || op["semantic"]!.GetValue<string>()!="literal_add")
                throw new ArgumentException("Unsupported operation semantic");
            allowed=allowed.Append("semantic").ToArray();
        }
        if (op.Any(p => !allowed.Contains(p.Key))) throw new ArgumentException("Unexpected operation field");
        foreach (string field in new[] { "path", "from", "to" }) if (op.ContainsKey(field) && (op[field] is not JsonArray path || !path.All(Scalar))) throw new ArgumentException("Path must contain scalar JSON tokens");
        if (two)
        {
            if (op["unlabeledPaths"] is not null)
            {
                if (op["unlabeledPaths"] is not JsonArray paths || paths.Count != 2 || !paths.All(p => p is JsonArray a && a.All(Scalar))) throw new ArgumentException("Invalid unlabeled paths");
            }
            else if (op["from"] is null || op["to"] is null) throw new ArgumentException("Missing directional path");
        }
        else if (op["unlabeledPathValue"] is null && (op["path"] is null || (name != "remove" && !op.ContainsKey("value")))) throw new ArgumentException("Missing path/value");
    }
    private static JsonObject LowerLiteralAdd(JsonObject op,JsonNode? state,IntentOptions options)
    {
        if(!op.ContainsKey("semantic")) return op;
        if(op["op"]?.GetValue<string>()!="append" || op["semantic"]?.GetValue<string>()!="literal_add")
            throw new ArgumentException("Unsupported operation semantic");
        var target=Resolve(state,Path(op,"path"),options);
        if(target.Node is JsonArray) op["op"]="append";
        else if(target.Parent is JsonObject) op["op"]="update";
        else throw new ArgumentException("Literal add requires a collection or existing object field");
        op.Remove("semantic");
        return op;
    }
    private static JsonObject Concrete(JsonObject raw, JsonNode? state, IntentOptions options)
    {
        var op = (JsonObject)JsonContract.Clone(raw)!;
        if (op["unlabeledPathValue"] is JsonArray candidates)
        {
            var valid = new List<JsonObject>();
            foreach (var candidate in candidates)
            {
                var trial = new JsonObject { ["op"] = JsonContract.Clone(op["op"]) };
                if (candidate is not JsonObject candidateObject) continue;
                foreach (var p in candidateObject) trial[p.Key] = JsonContract.Clone(p.Value);
                if(op.ContainsKey("semantic")) trial["semantic"]=JsonContract.Clone(op["semantic"]);
                try { ValidateShape(trial); LowerLiteralAdd(trial,state,options); Execute(JsonContract.Clone(state), trial, options); valid.Add(trial); } catch { }
            }
            if (valid.Count != 1) throw new ArgumentException("Unlabeled path/value must resolve uniquely");
            return valid[0];
        }
        if (op["unlabeledPaths"] is JsonArray paths)
        {
            var a = Resolve(state, (JsonArray)paths[0]!, options); var b = Resolve(state, (JsonArray)paths[1]!, options);
            if ((a.Node is JsonArray) == (b.Node is JsonArray)) throw new ArgumentException("Unlabeled source/destination ambiguous");
            op["from"] = JsonContract.Clone(paths[a.Node is JsonArray ? 1 : 0]); op["to"] = JsonContract.Clone(paths[a.Node is JsonArray ? 0 : 1]); op.Remove("unlabeledPaths");
        }
        return LowerLiteralAdd(op,state,options);
    }
    private static JsonArray Execute(JsonNode? state, JsonObject op, IntentOptions options)
    {
        string name = op["op"]!.GetValue<string>(); string idKey = string.IsNullOrEmpty(options.IdKey) ? "id" : options.IdKey;
        if (name is "copy" or "move")
        {
            var from = Path(op, "from"); var to = Path(op, "to"); var source = Resolve(state, from, options); var dest = Resolve(state, to, options);
            if (dest.Node is not JsonArray destination) throw new ArgumentException("Destination must be a collection");
            if (ReferenceEquals(source.Parent, destination)) throw new ArgumentException("Same-collection transfer unsupported");
            if (from.Count <= to.Count && from.Select((v, i) => JsonContract.TypedEquals(v, to[i])).All(v => v)) throw new ArgumentException("Transfer into source or descendant unsupported");
            CheckAppend(destination, source.Node, idKey);
            var patch = new JsonArray(new JsonObject { ["op"] = "add", ["path"] = Pointer(dest.Pointer) + "/-", ["value"] = JsonContract.Clone(source.Node) });
            destination.Add(JsonContract.Clone(source.Node));
            if (name == "move") { patch.Add(new JsonObject { ["op"] = "remove", ["path"] = Pointer(source.Pointer) }); Delete(source); }
            return patch;
        }
        var path = Path(op, "path"); var r = Resolve(state, path, options);
        if (name == "append")
        {
            if (r.Node is not JsonArray array) throw new ArgumentException("Append target must be collection");
            CheckAppend(array, op["value"], idKey); array.Add(JsonContract.Clone(op["value"]));
            return new JsonArray(new JsonObject { ["op"] = "add", ["path"] = Pointer(r.Pointer) + "/-", ["value"] = JsonContract.Clone(op["value"]) });
        }
        if (name == "update")
        {
            if (r.Parent is null) throw new ArgumentException("Root replacement unsupported");
            if (r.Key == idKey && r.Parent is JsonObject)
            {
                var parentPath = new JsonArray(path.Take(path.Count - 1).Select(JsonContract.Clone).ToArray()); var owner = Resolve(state, parentPath, options);
                if (owner.Parent is JsonArray owners)
                {
                    if (!Scalar(op["value"])) throw new ArgumentException("Object identities must be scalar JSON values");
                    if (HasIdentityCollision(owners.Where((_, i) => i.ToString(CultureInfo.InvariantCulture) != owner.Key), op["value"], idKey)) throw new ArgumentException("Identity update would create a duplicate");
                }
            }
            if (r.Parent is JsonArray array)
            {
                int index = int.Parse(r.Key!, CultureInfo.InvariantCulture);
                if (HasIdentityCollision(array.Where((_, i) => i != index), op["value"], idKey)) throw new ArgumentException("Update would create ambiguous duplicate identity");
                array[index] = JsonContract.Clone(op["value"]);
            }
            else ((JsonObject)r.Parent)[r.Key!] = JsonContract.Clone(op["value"]);
            return new JsonArray(new JsonObject { ["op"] = "replace", ["path"] = Pointer(r.Pointer), ["value"] = JsonContract.Clone(op["value"]) });
        }
        if (name == "remove") { Delete(r); return new JsonArray(new JsonObject { ["op"] = "remove", ["path"] = Pointer(r.Pointer) }); }
        throw new ArgumentException("Unsupported operation");
    }
    public static JsonArray ConvertIntent(JsonArray ir, JsonNode? input, IntentOptions? options = null)
    {
        options ??= new(); var state = JsonContract.Clone(input); var custom = new JsonArray(); var standard = new JsonArray();
        foreach (var raw in ir) { ValidateShape(raw); var op = Concrete((JsonObject)raw!, state, options); foreach (var patch in Execute(state, op, options)) standard.Add(patch!.DeepClone()); custom.Add(op); }
        return options.JsonPatch ? standard : custom;
    }
    public static JsonNode? ApplyPatch(JsonNode? input, JsonArray patch, IntentOptions? options = null)
    {
        options ??= new(); var state = JsonContract.Clone(input);
        foreach (var raw in patch) { ValidateShape(raw); var op = (JsonObject)raw!; if (op.ContainsKey("semantic") || op["unlabeledPaths"] is not null || op["unlabeledPathValue"] is not null) throw new ArgumentException("Custom patch must have resolved roles"); Execute(state, op, options); }
        return state;
    }
}
