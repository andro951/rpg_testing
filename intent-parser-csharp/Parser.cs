using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Csc592.IntentParser;

/// <summary>
/// Native implementation of the two published GrammarForge intent grammars.
/// The stages intentionally mirror parse.cjs: structural lexing, component grammar,
/// semantic intent, unique newline partitioning, and conservative outer recovery.
/// No JavaScript runtime or model inference is involved.
/// </summary>
public static partial class IntentParser
{
    private static readonly Dictionary<string, string> Operations = new(StringComparer.Ordinal)
    {
        ["add"]="append", ["append"]="append", ["insert"]="append", ["update"]="update",
        ["remove"]="remove", ["delete"]="remove", ["copy"]="copy", ["move"]="move"
    };
    private static readonly Dictionary<string, string> Labels = new(StringComparer.Ordinal)
    {
        ["op"]="op", ["operation"]="op", ["type"]="op", ["path"]="path", ["from"]="from",
        ["source"]="from", ["to"]="to", ["destination"]="to", ["value"]="value"
    };
    private static readonly Dictionary<char, char> Opens = new() { ['(']=')', ['[']=']', ['{']='}' };
    // ECMAScript's whitespace set, including BOM but excluding U+0085.
    private const string Ws = @"\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff";
    private const string StringPattern = "\"(?:[^\"\\\\\\r\\n]|\\\\.)*\"";
    private const string NumberPattern = @"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?";
    private static readonly string WordPattern = @"(?:(?!->)[^" + Ws + @"""(){}\[\],;:=/\.>])+";
    private sealed record LexRule(string Type, Regex Pattern, bool Ignore=false);
    private sealed record Token(string Type, string Text);
    private sealed record Node(string Type, string Text, char Open='\0', List<Node>? Children=null)
    {
        public bool IsGroup => Children is not null;
    }
    private static LexRule Rule(string type, string pattern, bool ignore=false, bool insensitive=false)
        => new(type, new Regex(@"\G(?:" + pattern + ")", RegexOptions.CultureInvariant | (insensitive ? RegexOptions.IgnoreCase : RegexOptions.None)), ignore);
    private static readonly List<LexRule> StructuralRules = new()
    {
        Rule("STRING", StringPattern), Rule("NUMBER", NumberPattern), Rule("DELIMITER", @"=>|->|:|="),
        Rule("WORD", WordPattern), Rule("PATH_SEPARATOR", @"\.|/"),
        Rule("LPAREN", @"\("), Rule("RPAREN", @"\)"), Rule("LBRACE", @"\{"), Rule("RBRACE", @"\}"),
        Rule("LBRACKET", @"\["), Rule("RBRACKET", @"\]"), Rule("SEP_COMMA", ","), Rule("SEMICOLON", ";"),
        Rule("HORIZONTAL_SPACE", @"[\u0009\u000b\u000c\u0020\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\ufeff]+", true),
        Rule("NEWLINE", @"\r\n|[\r\n\u2028\u2029]")
    };
    private static string LabelPattern(string names) => "(?:\"(?:"+names+")\"|(?:"+names+")(?![A-Za-z0-9_]))(?=["+Ws+"]*(?::|=|->))";
    private static readonly List<LexRule> ComponentRules = new()
    {
        Rule("OP_LABEL", LabelPattern("op|operation|type"), insensitive:true),
        Rule("PATH_LABEL", LabelPattern("path|from|source|to|destination"), insensitive:true),
        Rule("VALUE_LABEL", LabelPattern("value"), insensitive:true),
        Rule("OPERATION", @"(?:add|append|insert|update|remove|delete|copy|move)(?![A-Za-z0-9_])", insensitive:true),
        Rule("STRING", StringPattern), Rule("NUMBER", NumberPattern),
        Rule("BOOLEAN", @"(?:true|false)(?![A-Za-z0-9_])"), Rule("NULL", @"null(?![A-Za-z0-9_])"),
        Rule("DELIMITER", "=>|->|="), Rule("COLON", ":"), Rule("SLASH", "/"), Rule("PATH_SEPARATOR", @"\."),
        Rule("WORD", WordPattern), Rule("LPAREN", @"\("), Rule("RPAREN", @"\)"), Rule("LBRACE", @"\{"),
        Rule("RBRACE", @"\}"), Rule("LBRACKET", @"\["), Rule("RBRACKET", @"\]"), Rule("SEP_COMMA", ","),
        Rule("WHITESPACE", "["+Ws+"]+", true)
    };
    private static readonly List<LexRule> ValuePatchComponentRules = ComponentRules
        .Select(rule=>rule.Type=="OPERATION" ? Rule("OPERATION", @"(?:add|append|insert|update|replace|remove|delete|copy|move)(?![A-Za-z0-9_])", insensitive:true) : rule).ToList();
    private static List<Token> Lex(string text, List<LexRule> rules)
    {
        List<Token> result = new();
        for (int offset=0; offset<text.Length;)
        {
            bool found=false;
            foreach (var rule in rules)
            {
                Match match=rule.Pattern.Match(text,offset);
                if (!match.Success) continue;
                offset+=match.Length; found=true;
                if (!rule.Ignore) result.Add(new Token(rule.Type,match.Value));
                break;
            }
            if (!found) throw new InvalidOperationException($"Unexpected character at index {offset}");
        }
        return result;
    }
    private static List<Node> LexParse(string text)
    {
        var tokens=Lex(text,StructuralRules); int at=0;
        List<Node> Read(char? closer=null)
        {
            List<Node> nodes=new();
            while (at<tokens.Count)
            {
                Token token=tokens[at++];
                if (token.Text.Length==1 && Opens.TryGetValue(token.Text[0],out char close))
                    nodes.Add(new Node("GROUP","",token.Text[0],Read(close)));
                else if (token.Type is "RPAREN" or "RBRACE" or "RBRACKET")
                {
                    if (closer!=token.Text[0]) throw new InvalidOperationException("Mismatched grouping");
                    return nodes;
                }
                else
                {
                    if (token.Type is "NUMBER" or "STRING") ParseStrictJson(token.Text);
                    nodes.Add(new Node(token.Type,token.Text));
                }
            }
            if (closer is not null) throw new InvalidOperationException("Unbalanced grouping");
            return nodes;
        }
        return Read();
    }
    private static bool IsSep(Node x) => !x.IsGroup && x.Type is "SEP_COMMA" or "NEWLINE";
    private static string Render(Node x) => x.IsGroup ? x.Open+string.Join(" ",x.Children!.Select(Render))+Opens[x.Open] : x.Text;
    private static string TokenValue(Node x) => x.Type=="STRING" ? JsonSerializer.Deserialize<string>(x.Text)! : x.Text;
    private static string? Label(Node x) => !x.IsGroup && Labels.TryGetValue(TokenValue(x).ToLowerInvariant(), out string? label) ? label : null;
    private static string? CanonicalOperation(string word, IntentOptions options)
    {
        word=word.ToLowerInvariant();
        if(word=="replace" && options.PathSyntax=="value_patch") return "update";
        return Operations.GetValueOrDefault(word);
    }
    private static bool IsOperation(Node x,IntentOptions options) => x.Type=="WORD" && CanonicalOperation(x.Text,options) is not null;
    private static JsonNode? Scalar(Node x)
    {
        if (x.Type=="STRING") return JsonValue.Create(TokenValue(x));
        if (x.Type=="NUMBER" || x.Type=="WORD" && x.Text is "true" or "false" or "null") return ParseStrictJson(x.Text);
        return JsonValue.Create(x.Text);
    }
    private static JsonArray PathTokens(List<Node> input,IntentOptions options)
    {
        var xs=input; bool grouped=xs.Count==1 && xs[0].IsGroup;
        if (grouped) { xs=xs[0].Children!; if (xs.Count==0) return new JsonArray(); }
        if (xs.Count==1 && xs[0].Type=="STRING")
        {
            string text=TokenValue(xs[0]);
            if (!grouped && options.PathSyntax=="value_patch") return ValuePathTokens(text);
            if (!grouped && text.StartsWith('/'))
            {
                if (Regex.IsMatch(text,@"~(?:[^01]|$)")) throw new InvalidOperationException("Invalid JSON Pointer escape");
                return new JsonArray(text[1..].Split('/').Select(p=>(JsonNode?)JsonValue.Create(p.Replace("~1","/").Replace("~0","~"))).ToArray());
            }
            return new JsonArray(JsonValue.Create(text));
        }
        JsonArray output=new();
        foreach (var x in xs)
        {
            if (x.IsGroup) throw new InvalidOperationException("Nested path grouping is ambiguous");
            if (x.Type is "PATH_SEPARATOR" or "SEP_COMMA" or "NEWLINE") continue;
            if (x.Type is not ("STRING" or "WORD" or "NUMBER")) throw new InvalidOperationException("Invalid path token");
            output.Add(Scalar(x));
        }
        if (output.Count==0) throw new InvalidOperationException("Empty path requires explicit root representation");
        return output;
    }
    private static JsonArray ValuePathTokens(string path)
    {
        if(path=="") return new JsonArray();
        if(!path.StartsWith('/')) return new JsonArray(JsonValue.Create(path));
        JsonArray result=new(); int offset=1;
        while(true)
        {
            int end;
            if(offset<path.Length && path[offset]=='"')
            {
                end=offset+1; bool escaped=false,closed=false;
                while(end<path.Length)
                {
                    char c=path[end++];
                    if(escaped) escaped=false;
                    else if(c=='\\') escaped=true;
                    else if(c=='"') { closed=true; break; }
                }
                if(!closed) throw new ArgumentException("Invalid JSON string in value path");
                if(end<path.Length && path[end]!='/') throw new ArgumentException("A quoted path part must be followed by / or the end");
                result.Add(ParseStrictJson(path[offset..end]));
            }
            else
            {
                end=path.IndexOf('/',offset); if(end<0) end=path.Length;
                string part=path[offset..end];
                if(part is "true" or "false" or "null" || Regex.IsMatch(part,"^(?:"+NumberPattern+")$")) result.Add(ParseStrictJson(part));
                else
                {
                    if(Regex.IsMatch(part,@"~(?:[^01]|$)")) throw new ArgumentException("Invalid value path escape");
                    result.Add(JsonValue.Create(part.Replace("~1","/").Replace("~0","~")));
                }
            }
            if(end==path.Length) return result;
            offset=end+1;
        }
    }
    internal static JsonNode? ParseStrictJson(string text)
    {
        using JsonDocument doc=JsonDocument.Parse(text, new JsonDocumentOptions { MaxDepth=1024 });
        void Check(JsonElement item)
        {
            if (item.ValueKind==JsonValueKind.Object)
            {
                HashSet<string> keys=new(StringComparer.Ordinal);
                foreach (var property in item.EnumerateObject())
                {
                    if (!keys.Add(property.Name)) throw new InvalidOperationException("Duplicate JSON value key");
                    Check(property.Value);
                }
            }
            else if (item.ValueKind==JsonValueKind.Array) foreach (var value in item.EnumerateArray()) Check(value);
            else if (item.ValueKind==JsonValueKind.Number)
            {
                double number=item.GetDouble();
                if (!double.IsFinite(number) || double.IsInteger(number) && Math.Abs(number)>9007199254740991d)
                    throw new InvalidOperationException("Nonfinite or unsafe JSON number");
            }
        }
        Check(doc.RootElement);
        return JsonContract.Clone(JsonNode.Parse(text, documentOptions:new JsonDocumentOptions { MaxDepth=1024 }));
    }
    private static JsonNode? ValueOf(List<Node> xs)
    {
        if (xs.Count==0) throw new InvalidOperationException("Missing value");
        return ParseStrictJson(string.Join(" ",xs.Select(Render)));
    }
    // The component grammar is ordered-choice, like the upstream GrammarForge parser.
    private sealed class ComponentParser
    {
        private readonly List<Token> tokens;
        private int at;
        public ComponentParser(string text,IntentOptions options) { tokens=Lex(text,options.PathSyntax=="value_patch"?ValuePatchComponentRules:ComponentRules); }
        private bool Eat(params string[] types)
        {
            if (at>=tokens.Count || !types.Contains(tokens[at].Type)) return false;
            at++; return true;
        }
        private bool Attempt(Func<bool> parse)
        {
            int start=at;
            if (parse()) return true;
            at=start; return false;
        }
        private bool OperationType() => Eat("OPERATION","STRING");
        private bool Delimiter() => Eat("COLON","DELIMITER");
        private bool PathPart() => Eat("STRING","NUMBER","WORD","OPERATION","BOOLEAN","NULL");
        private bool GroupedPath()
        {
            if (at>=tokens.Count) return false;
            string? close=tokens[at].Type switch { "LPAREN"=>"RPAREN", "LBRACKET"=>"RBRACKET", "LBRACE"=>"RBRACE", _=>null };
            if (close is null) return false;
            at++;
            while (PathPart()) Eat("SLASH","PATH_SEPARATOR","SEP_COMMA");
            return Eat(close);
        }
        private bool ScalarPath()
        {
            Eat("SLASH");
            if (!PathPart()) return false;
            while (Attempt(()=>Eat("SLASH","PATH_SEPARATOR") && PathPart())) { }
            return true;
        }
        private bool Path() => Attempt(GroupedPath) || Attempt(ScalarPath);
        private bool JsonObject()
        {
            if (!Eat("LBRACE")) return false;
            if (Eat("RBRACE")) return true;
            if (!Member()) return false;
            while (Attempt(()=>Eat("SEP_COMMA") && Member())) { }
            return Eat("RBRACE");
        }
        private bool Member() => Eat("STRING","OP_LABEL","PATH_LABEL","VALUE_LABEL") && Eat("COLON") && JsonValueRule();
        private bool JsonArrayRule()
        {
            if (!Eat("LBRACKET")) return false;
            if (Eat("RBRACKET")) return true;
            if (!JsonValueRule()) return false;
            while (Attempt(()=>Eat("SEP_COMMA") && JsonValueRule())) { }
            return Eat("RBRACKET");
        }
        private bool JsonValueRule() => Attempt(JsonObject) || Attempt(JsonArrayRule) || Eat("STRING","NUMBER","BOOLEAN","NULL");
        private bool Component()
            => Attempt(()=>Eat("OP_LABEL") && Delimiter() && OperationType())
            || Attempt(()=>Eat("PATH_LABEL") && Delimiter() && Path())
            || Attempt(()=>Eat("VALUE_LABEL") && Delimiter() && JsonValueRule())
            || Attempt(OperationType) || Attempt(JsonValueRule) || Attempt(Path);
        public List<List<Node>> Parse()
        {
            List<List<Node>> components=new();
            while (at<tokens.Count)
            {
                int start=at;
                if (!Component()) throw new InvalidOperationException("Invalid operation component");
                components.Add(LexParse(string.Join(" ",tokens.Skip(start).Take(at-start).Select(t=>t.Text))));
            }
            if (components.Count==0) throw new InvalidOperationException("Missing operation components");
            return components;
        }
    }
    private static JsonObject ParseRecord(List<Node> source,IntentOptions options)
    {
        var xs=source.Where(x=>!IsSep(x)).ToList();
        var components=new ComponentParser(string.Join(" ",xs.Select(Render)),options).Parse();
        Dictionary<string,List<Node>> fields=new(StringComparer.Ordinal); List<Node> unlabeled=new();
        foreach (var items in components)
        {
            string? key=Label(items[0]);
            if (key is not null && items.Count>1 && items[1].Type=="DELIMITER")
            {
                if (!fields.TryAdd(key,items.Skip(2).ToList())) throw new InvalidOperationException("Duplicate "+key+" label");
            }
            else unlabeled.AddRange(items);
        }
        if (!fields.ContainsKey("op") && !unlabeled.Any(x=>IsOperation(x,options)))
        {
            List<(string key,int index,Node node)> candidates=new();
            foreach (string key in new[]{"path","from","to"}) if (fields.TryGetValue(key,out var values))
                for (int i=0;i<values.Count;i++) if (IsOperation(values[i],options) && (i==0 || values[i-1].Type!="PATH_SEPARATOR") && (i+1==values.Count || values[i+1].Type!="PATH_SEPARATOR"))
                    candidates.Add((key,i,values[i]));
            if (candidates.Count==1)
            {
                var candidate=candidates[0]; fields[candidate.key].RemoveAt(candidate.index); unlabeled.Add(candidate.node);
            }
        }
        string? op;
        if (fields.TryGetValue("op",out var operation))
        {
            if (operation.Count!=1) throw new InvalidOperationException("Exactly one operation type required");
            op=CanonicalOperation(TokenValue(operation[0]),options);
        }
        else
        {
            var positions=Enumerable.Range(0,unlabeled.Count).Where(i=>IsOperation(unlabeled[i],options)).ToList();
            if (positions.Count==0) positions=Enumerable.Range(0,unlabeled.Count).Where(i=>unlabeled[i].Type=="STRING" && CanonicalOperation(TokenValue(unlabeled[i]),options) is not null).ToList();
            if (positions.Count!=1) throw new InvalidOperationException("Exactly one unambiguous operation type required");
            op=CanonicalOperation(TokenValue(unlabeled[positions[0]]),options); unlabeled.RemoveAt(positions[0]);
        }
        if (op is null) throw new InvalidOperationException("Unsupported or ambiguous operation alias");
        JsonObject ir=new() { ["op"]=op };
        foreach (string key in new[]{"path","from","to"}) if (fields.TryGetValue(key,out var value)) ir[key]=PathTokens(value,options);
        if (fields.TryGetValue("value",out var literal)) ir["value"]=ValueOf(literal);
        if (op is "append" or "update" && unlabeled.Count>0)
        {
            if (ir.ContainsKey("path") && !ir.ContainsKey("value")) { ir["value"]=ValueOf(unlabeled); unlabeled.Clear(); }
            else if (!ir.ContainsKey("path") && !ir.ContainsKey("value"))
            {
                Dictionary<string,JsonObject> unique=new(StringComparer.Ordinal);
                for (int split=1;split<unlabeled.Count;split++)
                {
                    var left=unlabeled.Take(split).ToList(); var right=unlabeled.Skip(split).ToList();
                    foreach (var (path,value) in new[]{(left,right),(right,left)})
                        try
                        {
                            JsonObject candidate=new() { ["path"]=PathTokens(path,options), ["value"]=ValueOf(value) };
                            unique[JsonContract.Stringify(candidate)]=candidate;
                        }
                        catch (Exception e) when (e is InvalidOperationException or JsonException or ArgumentException) { }
                }
                if (unique.Count==0) throw new InvalidOperationException("Cannot distinguish unlabeled path and JSON value");
                ir["unlabeledPathValue"]=new JsonArray(unique.Values.Select(c=>(JsonNode)c).ToArray()); unlabeled.Clear();
            }
        }
        if (unlabeled.Count>0)
        {
            if (op is "copy" or "move" && !ir.ContainsKey("path") && ir.ContainsKey("from")!=ir.ContainsKey("to") && unlabeled.Count==1 && (unlabeled[0].IsGroup || unlabeled[0].Type=="STRING"))
            { ir[ir.ContainsKey("from")?"to":"from"]=PathTokens(unlabeled,options); unlabeled.Clear(); }
            if (unlabeled.Count>0 && (ir.ContainsKey("path") || ir.ContainsKey("from") || ir.ContainsKey("to"))) throw new InvalidOperationException("Unlabeled component conflicts with labeled paths");
            if (unlabeled.Count>0 && op is "copy" or "move")
            {
                if (unlabeled.Count!=2 || !unlabeled.All(x=>x.IsGroup || x.Type=="STRING")) throw new InvalidOperationException("Two unlabeled paths require explicit grouping or quoting");
                ir["unlabeledPaths"]=new JsonArray(unlabeled.Select(x=>(JsonNode)PathTokens(new(){x},options)).ToArray());
            }
            else if (unlabeled.Count>0) ir["path"]=PathTokens(unlabeled,options);
        }
        if (op is "copy" or "move")
        {
            if (ir.ContainsKey("value")) throw new InvalidOperationException("Copy/move use source path, not value");
            if (ir.ContainsKey("path"))
            {
                string role=ir.ContainsKey("from") && !ir.ContainsKey("to") ? "to" : ir.ContainsKey("to") && !ir.ContainsKey("from") ? "from" : throw new InvalidOperationException("Copy/move path role ambiguous");
                var path=ir["path"]; ir.Remove("path"); ir[role]=path;
            }
            if (!ir.ContainsKey("unlabeledPaths") && (!ir.ContainsKey("from") || !ir.ContainsKey("to"))) throw new InvalidOperationException("Copy/move needs source and destination");
        }
        else
        {
            if (ir.ContainsKey("from") || ir.ContainsKey("to")) throw new InvalidOperationException("Directional paths not valid for this operation");
            if (!ir.ContainsKey("path") && !ir.ContainsKey("unlabeledPathValue")) throw new InvalidOperationException("Missing path");
            if (op=="remove" && ir.ContainsKey("value")) throw new InvalidOperationException("Remove cannot carry a value");
            if (op!="remove" && !ir.ContainsKey("value") && !ir.ContainsKey("unlabeledPathValue")) throw new InvalidOperationException("Missing value");
        }
        return ir;
    }
    private static (string text,string? repair) RepairOuterWrapper(string text, IntentOptions options)
    {
        List<(char c,int index)> stack=new(), unmatched=new(); bool quoted=false,escaped=false;
        for (int i=0;i<text.Length;i++)
        {
            char c=text[i];
            if (quoted) { if (escaped) escaped=false; else if (c=='\\') escaped=true; else if(c=='"') quoted=false; continue; }
            if (c=='"') { quoted=true; continue; }
            if (Opens.ContainsKey(c)) { stack.Add((c,i)); if(stack.Count>options.MaxDepth) throw new InvalidOperationException("Grouping depth limit exceeded"); }
            else if (Opens.ContainsValue(c))
            {
                if (stack.Count>0) { if(Opens[stack[^1].c]!=c) throw new InvalidOperationException("Mismatched grouping"); stack.RemoveAt(stack.Count-1); }
                else unmatched.Add((c,i));
            }
        }
        if (quoted) throw new InvalidOperationException("Unterminated quoted value");
        int first=Regex.Match(text,"[^"+Ws+"]").Index;
        if (stack.Count==1 && unmatched.Count==0 && stack[0].index==first) return (text+Opens[stack[0].c],"missing outer closer");
        int end=text.Length; while(end>0 && Regex.IsMatch(text[end-1].ToString(),"^["+Ws+"]$")) end--;
        if (stack.Count==0 && unmatched.Count==1 && unmatched[0].index==end-1) return (Opens.Single(p=>p.Value==unmatched[0].c).Key+text,"missing outer opener");
        if (stack.Count>0 || unmatched.Count>0) throw new InvalidOperationException("Unbalanced inner grouping cannot be safely recovered");
        return (text,null);
    }
    private static bool HasOperation(Node node,IntentOptions options)
        => node.Children!.Select((x,i)=>x.IsGroup ? HasOperation(x,options) : IsOperation(x,options) || x.Type=="STRING" && CanonicalOperation(TokenValue(x),options) is not null || Label(x)=="op" && i+1<node.Children!.Count && node.Children[i+1].Type=="DELIMITER").Any(x=>x);
    private static List<JsonObject> ParseSequence(List<Node> xs,IntentOptions options)
    {
        int first=xs.FindIndex(x=>!IsSep(x)); if(first<0) return new();
        int last=xs.Count; while(last>first && IsSep(xs[last-1])) last--;
        List<Node> compact=new(), separatorRun=new();
        void FlushSeparators() { if(separatorRun.Count>0) compact.Add(separatorRun.FirstOrDefault(x=>x.Type=="NEWLINE")??separatorRun[0]); separatorRun.Clear(); }
        foreach(var node in xs.GetRange(first,last-first)) { if(IsSep(node)) separatorRun.Add(node); else { FlushSeparators(); compact.Add(node); } }
        FlushSeparators(); xs=compact;
        if (xs.Any(x=>x.Type=="SEMICOLON"))
        {
            List<JsonObject> result=new(); List<Node> segment=new();
            foreach (var x in xs.Append(new Node("SEMICOLON",";")))
                if (x.Type=="SEMICOLON") { if(segment.Any(n=>!IsSep(n))) result.AddRange(ParseSequence(segment,options)); segment=new(); }
                else segment.Add(x);
            if (result.Count>options.MaxOperations) throw new InvalidOperationException("Operation count limit exceeded");
            return result;
        }
        List<int> boundaries=new(){0};
        for(int i=0;i<xs.Count;i++) if(xs[i].Type=="NEWLINE") boundaries.Add(i+1);
        if(boundaries[^1]!=xs.Count) boundaries.Add(xs.Count);
        int attempts=0; Dictionary<int,List<List<JsonObject>>> memo=new();
        List<List<JsonObject>> Solve(int start)
        {
            if(start==xs.Count) return new(){new()};
            if(memo.TryGetValue(start,out var cached)) return cached;
            Dictionary<string,List<JsonObject>> results=new(StringComparer.Ordinal);
            foreach(int end in boundaries)
            {
                if(end<=start) continue;
                var part=xs.GetRange(start,end-start);
                if(!part.Any(x=>!IsSep(x))) { foreach(var tail in Solve(end)) results[JsonSerializer.Serialize(tail)]=tail; continue; }
                if(++attempts>options.MaxBoundaryAttempts) throw new InvalidOperationException("Operation boundary complexity limit exceeded; use explicit groups or semicolons");
                JsonObject operation;
                try { operation=ParseRecord(part,options); }
                catch(Exception e) when(e is InvalidOperationException or JsonException or ArgumentException) { continue; }
                foreach(var tail in Solve(end))
                {
                    if(tail.Count>=options.MaxOperations) throw new InvalidOperationException("Operation count limit exceeded");
                    var candidate=new List<JsonObject>(){operation}; candidate.AddRange(tail);
                    results[JsonSerializer.Serialize(candidate)]=candidate;
                    if(results.Count>1) break;
                }
                if(results.Count>1) break;
            }
            var value=results.Values.ToList(); memo[start]=value; return value;
        }
        var candidates=Solve(0);
        if(candidates.Count!=1) throw new InvalidOperationException(candidates.Count>0?"Ambiguous newline operation boundaries":"No complete operation sequence");
        return candidates[0];
    }
    public static JsonArray ParseIntent(string text,IntentOptions? options=null)
        => (JsonArray)ParseIntentWithDiagnostics(text,options)["operations"]!.DeepClone();
    public static JsonObject ParseIntentWithDiagnostics(string text,IntentOptions? options=null)
    {
        ArgumentNullException.ThrowIfNull(text); options??=new();
        if(text.Length>options.MaxChars) throw new InvalidOperationException("Intent text size limit exceeded");
        var fence=Regex.Match(text,"^["+Ws+"]*```(?:json)?[ \\t]*\\r?\\n([\\s\\S]*?)\\r?\\n```[ \\t]*["+Ws+"]*$",RegexOptions.IgnoreCase|RegexOptions.CultureInvariant);
        JsonArray diagnostics=new();
        if(fence.Success) { text=fence.Groups[1].Value; diagnostics.Add(new JsonObject(){["code"]="MARKDOWN_FENCE_REMOVED",["detail"]="single enclosing JSON code fence"}); }
        var repaired=RepairOuterWrapper(text,options);
        var tree=LexParse(repaired.text); var meaningful=tree.Where(x=>!IsSep(x)).ToList();
        if(repaired.repair is not null) diagnostics.Add(new JsonObject(){["code"]="OUTER_GROUP_RECOVERED",["detail"]=repaired.repair});
        if(meaningful.Count==1 && meaningful[0].IsGroup && meaningful[0].Children!.All(IsSep)) return new JsonObject(){["operations"]=new JsonArray(),["diagnostics"]=diagnostics};
        Dictionary<string,List<JsonObject>> candidates=new(StringComparer.Ordinal);
        void Accept(List<JsonObject> records)
        {
            if(records.Count>options.MaxOperations) throw new InvalidOperationException("Operation count limit exceeded");
            candidates[JsonSerializer.Serialize(records)]=records;
        }
        static bool Recoverable(Exception e) => (e is InvalidOperationException or JsonException or ArgumentException) && !e.Message.Contains("limit exceeded") && !e.Message.Contains("Ambiguous");
        try { Accept(ParseSequence(tree,options)); } catch(Exception e) when(Recoverable(e)) { }
        try
        {
            List<JsonObject> records=new(); List<Node> current=new();
            void Flush() { if(current.Any(x=>!IsSep(x))) records.AddRange(ParseSequence(current,options)); current=new(); }
            foreach(var node in tree)
            {
                if(node.Type=="SEMICOLON") { Flush(); continue; }
                if(node.IsGroup && current.All(IsSep) && HasOperation(node,options))
                {
                    Flush(); var inner=node.Children!.Where(x=>!IsSep(x)).ToList();
                    if(inner.Count>0 && inner.All(x=>x.IsGroup)) foreach(var child in inner) records.Add(ParseRecord(child.Children!,options));
                    else records.AddRange(ParseSequence(node.Children!,options));
                }
                else current.Add(node);
            }
            Flush(); Accept(records);
        }
        catch(Exception e) when(Recoverable(e)) { }
        if(candidates.Count!=1) throw new InvalidOperationException(candidates.Count>0?"Ambiguous complete operation interpretations":"No complete operation sequence");
        return new JsonObject(){["operations"]=new JsonArray(candidates.Values.First().Select(x=>(JsonNode)x).ToArray()),["diagnostics"]=diagnostics};
    }

    public static JsonArray NormalizeIntent(string text,JsonNode? document,IntentOptions? options=null)
        => ConvertIntent(ParseIntent(text,options),document,options);
}
