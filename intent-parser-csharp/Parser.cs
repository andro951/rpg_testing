using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Csc592.IntentParser;

/// <summary>
/// Native interpreter of the generated GrammarForge expression specification.
/// Complete program and operation ASTs drive conversion; bounded newline
/// partitioning is only an ambiguity check after conservative outer recovery.
/// No JavaScript runtime or model inference is involved.
/// </summary>
public static partial class IntentParser
{
    private static readonly Dictionary<string, string> Operations = new(StringComparer.Ordinal)
    {
        ["add"]="append", ["append"]="append", ["insert"]="append", ["update"]="update",
        ["set"]="update", ["change"]="update", ["remove"]="remove", ["delete"]="remove", ["copy"]="copy", ["move"]="move"
    };
    private static readonly Dictionary<string, string> Labels = new(StringComparer.Ordinal)
    {
        ["op"]="op", ["operation"]="op", ["type"]="op", ["path"]="path", ["from"]="from",
        ["source"]="from", ["to"]="to", ["destination"]="to", ["value"]="value"
    };
    private static readonly Dictionary<char, char> Opens = new() { ['(']=')', ['[']=']', ['{']='}' };
    // ECMAScript's whitespace set, including BOM but excluding U+0085.
    private const string Ws = @"\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff";
    private const string NumberPattern = @"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?";
    private sealed record LexRule(string Type, Regex Pattern, bool Ignore=false);
    private sealed record Token(string Type, string Text, int Start, int End);
    private sealed record Node(string Type, string Text, char Open='\0', List<Node>? Children=null)
    {
        public bool IsGroup => Children is not null;
    }
    private sealed record GrammarNode(string Name, int Start, int End, List<GrammarNode> Children);
    private sealed record GrammarTree(List<Token> Tokens, GrammarNode Root, string Text);
    private static readonly JsonDocument GrammarSpec = LoadGrammarSpec();
    private static JsonDocument LoadGrammarSpec()
    {
        using var stream=typeof(IntentParser).Assembly.GetManifestResourceStream("Csc592.IntentParser.grammar-spec.json")
            ?? throw new InvalidOperationException("Missing generated grammar specification");
        return JsonDocument.Parse(stream);
    }
    private static string NativePattern(string source)
    {
        // Preserve ECMAScript whitespace rather than .NET's Unicode class.
        source=source.Replace(@"[^\S\r\n\u2028\u2029]", @"[\u0009\u000b\u000c\u0020\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\ufeff]");
        var result=new System.Text.StringBuilder(); bool inClass=false;
        for(int i=0;i<source.Length;i++)
        {
            char c=source[i];
            if(c=='\\' && i+1<source.Length)
            {
                char next=source[++i];
                if(next=='s') result.Append(inClass?Ws:"["+Ws+"]");
                else if(next=='S') result.Append("[^"+Ws+"]");
                else if(next=='/') result.Append('/');
                else { result.Append('\\'); result.Append(next); }
            }
            else { if(c=='[') inClass=true; else if(c==']') inClass=false; result.Append(c); }
        }
        return result.ToString();
    }
    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string,List<LexRule>> GrammarLexerCache=new();
    private static List<LexRule> GrammarLexRules(string name,IntentOptions options)
        => GrammarLexerCache.GetOrAdd(name+":"+options.PathSyntax,_=>BuildGrammarLexRules(name,options));
    private static List<LexRule> BuildGrammarLexRules(string name,IntentOptions options)
    {
        List<LexRule> result=new();
        foreach(var token in GrammarSpec.RootElement.GetProperty("grammars").GetProperty(name).GetProperty("tokens").EnumerateArray())
        {
            string type=token.GetProperty("type").GetString()!,source=token.GetProperty("source").GetString()!;
            if(options.PathSyntax=="value_patch")
            {
                if(type=="UPDATE") source=@"(?:update|replace|set)\b";
                if(type=="Q_UPDATE") source="\"(?:update|replace|set)\"";
            }
            var flags=RegexOptions.CultureInvariant|RegexOptions.ECMAScript;
            if(token.GetProperty("flags").GetString()!.Contains('i')) flags|=RegexOptions.IgnoreCase;
            result.Add(new LexRule(type,new Regex(@"\G(?:"+NativePattern(source)+")",flags),token.GetProperty("tag").GetString()=="IGNORE"));
        }
        return result;
    }
    private static GrammarTree ParseGrammar(string name,string text,IntentOptions options)
    {
        var grammar=GrammarSpec.RootElement.GetProperty("grammars").GetProperty(name);
        var rules=grammar.GetProperty("rules"); var tokens=Lex(text,GrammarLexRules(name,options));
        // Both descent and continuation return run on this explicit work stack.
        // Right-recursive programs cannot consume the CLR call stack before limits.
        Stack<Action> work=new();
        void Schedule(JsonElement expression,int at,List<GrammarNode> output,Action<int?> done)
        {
            work.Push(()=>
            {
                int mark=output.Count;
                void Finish(int? result)
                {
                    if(result is null && output.Count>mark) output.RemoveRange(mark,output.Count-mark);
                    work.Push(()=>done(result));
                }
                if(expression.ValueKind==JsonValueKind.String)
                {
                    string reference=expression.GetString()!;
                    if(rules.TryGetProperty(reference,out var rule))
                    {
                        List<GrammarNode> children=new();
                        Schedule(rule,at,children,end=>
                        {
                            if(end is not null) output.Add(new GrammarNode(reference,at,end.Value,children));
                            Finish(end);
                        });
                    }
                    else Finish(at<tokens.Count && tokens[at].Type==reference ? at+1 : null);
                    return;
                }
                string kind=expression[0].GetString()!; var inner=expression[1];
                if(kind=="|")
                {
                    int alternative=0;
                    void Next()
                    {
                        if(alternative==inner.GetArrayLength()) { Finish(null); return; }
                        Schedule(inner[alternative++],at,output,end=> { if(end is not null) Finish(end); else Next(); });
                    }
                    Next(); return;
                }
                if(kind==",")
                {
                    int part=0,index=at;
                    void Next()
                    {
                        if(part==inner.GetArrayLength()) { Finish(index); return; }
                        Schedule(inner[part++],index,output,end=> { if(end is null) Finish(null); else { index=end.Value; Next(); } });
                    }
                    Next(); return;
                }
                int current=at;
                void Repeat()
                {
                    int before=output.Count;
                    Schedule(inner,current,output,end=>
                    {
                        if(end is null || end==current)
                        {
                            if(output.Count>before) output.RemoveRange(before,output.Count-before);
                            Finish(kind=="+" && current==at ? null : current); return;
                        }
                        current=end.Value;
                        if(kind=="?") Finish(current); else Repeat();
                    });
                }
                Repeat();
            });
        }
        string start=grammar.GetProperty("start").GetString()!;
        List<GrammarNode> children=new(); int? end=null;
        Schedule(rules.GetProperty(start),0,children,result=>end=result);
        while(work.Count>0) work.Pop()();
        if(end!=tokens.Count) throw new InvalidOperationException("No complete "+name+" grammar parse");
        return new GrammarTree(tokens,new GrammarNode(start,0,end.Value,children),text);
    }
    private static IEnumerable<GrammarNode> GrammarDescendants(GrammarNode root)
    {
        Stack<GrammarNode> pending=new(); pending.Push(root);
        while(pending.Count>0)
        {
            var node=pending.Pop(); yield return node;
            for(int i=node.Children.Count-1;i>=0;i--) pending.Push(node.Children[i]);
        }
    }
    private static string GrammarText(GrammarTree tree,GrammarNode node)
        => string.Join(" ",tree.Tokens.Skip(node.Start).Take(node.End-node.Start).Select(t=>t.Text));
    private static string GrammarRaw(GrammarTree tree,GrammarNode node)
        => node.Start==node.End?"":tree.Text[tree.Tokens[node.Start].Start..tree.Tokens[node.End-1].End];
    private static List<Token> Lex(string text, List<LexRule> rules)
    {
        List<Token> result = new();
        for (int offset=0; offset<text.Length;)
        {
            bool found=false;
            foreach (var rule in rules)
            {
                Match match=rule.Pattern.Match(text,offset);
                if (!match.Success || match.Length==0) continue;
                offset+=match.Length; found=true;
                if (!rule.Ignore) result.Add(new Token(rule.Type,match.Value,offset-match.Length,offset));
                break;
            }
            if (!found) throw new InvalidOperationException($"Unexpected character at index {offset}");
        }
        return result;
    }
    private static List<Node> LexParse(string text)
    {
        var tree=ParseGrammar("tokens",text,new IntentOptions());
        List<Node> Convert(GrammarNode node)
        {
            if(node.Name=="group") return new(){new Node("GROUP","",tree.Tokens[node.Start].Text[0],node.Children.SelectMany(Convert).ToList())};
            if(node.Name=="atom")
            {
                var token=tree.Tokens[node.Start];
                if(token.Type is "NUMBER" or "STRING") ParseStrictJson(token.Text);
                return new(){new Node(token.Type,token.Text)};
            }
            return node.Children.SelectMany(Convert).ToList();
        }
        return Convert(tree.Root);
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
    private static List<List<Node>> Components(GrammarTree tree,GrammarNode root)
    {
        List<List<Node>> result=new();
        void Collect(GrammarNode node)
        {
            if(node.Name.EndsWith("_component",StringComparison.Ordinal))
            { result.Add(LexParse(GrammarText(tree,node)).Where(x=>!IsSep(x)).ToList()); return; }
            foreach(var child in node.Children) Collect(child);
        }
        Collect(root); return result;
    }
    private static JsonObject ParseRecord(List<Node> source,IntentOptions options)
    {
        var xs=source.Where(x=>!IsSep(x)).ToList();
        var tree=ParseGrammar("operation",string.Join(" ",xs.Select(Render)),options);
        return ConvertOperation(tree,tree.Root,options);
    }
    private static JsonNode? TypedValue(GrammarTree tree,GrammarNode root,IntentOptions options)
    {
        var typed=GrammarDescendants(root).FirstOrDefault(n=>n.Name.StartsWith("typed_",StringComparison.Ordinal));
        if(typed is null)
        {
            var value=GrammarDescendants(root).First(n=>n.Name=="json_value");
            return ParseStrictJson(GrammarRaw(tree,value));
        }
        if(typed.Name=="typed_text")
        {
            int start=tree.Tokens[typed.Start+1].End;
            int end=start;
            while(end<tree.Text.Length && tree.Text[end] is not ('\r' or '\n' or '\u2028' or '\u2029')) end++;
            string text=tree.Text[start..end];
            if(options.OutputFormat=="typed_lines" && text.StartsWith(' ')) text=text[1..];
            if(options.OutputFormat is "literal_line" or "end_marked_line")
            {
                if(options.OutputFormat=="end_marked_line")
                {
                    if(!text.EndsWith('|')) throw new InvalidOperationException("Text value needs a final end marker");
                    text=text[..^1];
                }
                var decoded=new System.Text.StringBuilder();
                for(int i=0;i<text.Length;i++)
                {
                    if(text[i]!='\\') { decoded.Append(text[i]); continue; }
                    if(++i==text.Length) throw new InvalidOperationException("Incomplete text escape");
                    decoded.Append(text[i] switch {
                        '\\'=>'\\', 'n'=>'\n', 'r'=>'\r', 't'=>'\t',
                        's' when options.OutputFormat=="literal_line"=>' ',
                        '"' when options.OutputFormat=="literal_line"=>'"',
                        _=>throw new InvalidOperationException("Invalid text escape")
                    });
                }
                text=decoded.ToString();
            }
            var value=JsonValue.Create(text);
            JsonContract.AssertJson(value);
            return value;
        }
        string raw=GrammarRaw(tree,typed);
        string payload=raw[(raw.IndexOf(':')+1)..].Trim();
        if(typed.Name=="typed_null") return null;
        if(typed.Name=="typed_object" && payload.Length==0) return new JsonObject();
        if(typed.Name=="typed_list" && payload.Length==0) return new JsonArray();
        if(typed.Name=="typed_number")
        {
            if(!Regex.IsMatch(payload,@"^(?:"+NumberPattern+@"|\+(?!-)"+NumberPattern+@")$"))
                throw new InvalidOperationException("Typed numbers require a complete finite JSON number");
            if(payload.StartsWith('+')) payload=payload[1..];
        }
        var result=ParseStrictJson(payload);
        if(typed.Name=="typed_json" && result is JsonValue scalar && scalar.TryGetValue<string>(out _))
            throw new InvalidOperationException("json: does not accept a string value");
        return result;
    }
    private static JsonObject ConvertLineOperation(GrammarTree tree,GrammarNode root,IntentOptions options)
    {
        var nodes=GrammarDescendants(root).ToList();
        string word=tree.Tokens[root.Start].Text.ToLowerInvariant();
        string op=CanonicalOperation(word,options)??throw new InvalidOperationException("Unsupported line operation");
        JsonArray Path(string role)
        {
            var node=nodes.First(n=>n.Name==role);
            var slash=GrammarDescendants(node).FirstOrDefault(n=>n.Name=="line_slash_path");
            if(slash is not null)
            {
                int start=tree.Tokens[slash.Start].Start,end=tree.Tokens[slash.End-1].End;
                if(root.Name=="line_remove" || nodes.Any(n=>n.Name is "header_write" or "header_transfer"))
                    while(end<tree.Text.Length && tree.Text[end] is not ('\r' or '\n' or '\u2028' or '\u2029')
                        && Regex.IsMatch(tree.Text[end].ToString(),"^["+Ws+"]$")) end++;
                return ValuePathTokens(tree.Text[start..end]);
            }
            return PathTokens(LexParse(GrammarRaw(tree,node)).Where(n=>!IsSep(n)).ToList(),options);
        }
        JsonObject result=new(){["op"]=op};
        if(root.Name=="line_transfer")
        {
            result["from"]=Path("line_source"); result["to"]=Path("line_destination");
        }
        else
        {
            result["path"]=Path("line_target");
            if(root.Name=="line_write") result["value"]=TypedValue(tree,nodes.First(n=>n.Name=="line_value"),options);
        }
        if(word=="add") result["semantic"]="literal_add";
        if(word=="change")
        {
            if(!nodes.Any(n=>n.Name=="typed_number")) throw new InvalidOperationException("change requires a typed number value");
            result["semantic"]="numeric_delta";
        }
        if(op=="remove" && options.OutputFormat=="typed_lines") result["semantic"]="typed_remove";
        return result;
    }
    private static JsonObject ConvertOperation(GrammarTree tree,GrammarNode root,IntentOptions options)
    {
        var line=GrammarDescendants(root).FirstOrDefault(n=>n.Name is "line_write" or "line_remove" or "line_transfer");
        if(line is not null) return ConvertLineOperation(tree,line,options);
        var components=Components(tree,root);
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
        string? op; string originalWord;
        if (fields.TryGetValue("op",out var operation))
        {
            if (operation.Count!=1) throw new InvalidOperationException("Exactly one operation type required");
            originalWord=TokenValue(operation[0]);
            op=CanonicalOperation(originalWord,options);
        }
        else
        {
            var positions=Enumerable.Range(0,unlabeled.Count).Where(i=>IsOperation(unlabeled[i],options)).ToList();
            if (positions.Count==0) positions=Enumerable.Range(0,unlabeled.Count).Where(i=>unlabeled[i].Type=="STRING" && CanonicalOperation(TokenValue(unlabeled[i]),options) is not null).ToList();
            if (positions.Count!=1) throw new InvalidOperationException("Exactly one unambiguous operation type required");
            originalWord=TokenValue(unlabeled[positions[0]]);
            op=CanonicalOperation(originalWord,options); unlabeled.RemoveAt(positions[0]);
        }
        if (op is null) throw new InvalidOperationException("Unsupported or ambiguous operation alias");
        JsonObject ir=new() { ["op"]=op };
        if(originalWord.Equals("add",StringComparison.OrdinalIgnoreCase)) ir["semantic"]="literal_add";
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
        if(op=="remove" && options.OutputFormat=="typed_lines") ir["semantic"]="typed_remove";
        return ir;
    }
    private static (string text,string? repair) RepairOuterWrapper(string text, IntentOptions options, GrammarTree? tree=null)
    {
        string original=text;
        // Only grammar-proven text values are opaque to structural checks.
        var masked=text.ToCharArray();
        if(tree is not null)
            foreach(var node in GrammarDescendants(tree.Root).Where(n=>n.Name=="typed_text"))
            {
                int start=tree.Tokens[node.Start].Start,textEnd=tree.Tokens[node.Start+1].End;
                while(textEnd<text.Length && text[textEnd] is not ('\r' or '\n' or '\u2028' or '\u2029')) textEnd++;
                Array.Fill(masked,' ',start,textEnd-start);
            }
        text=new string(masked);
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
        if (stack.Count==1 && unmatched.Count==0 && stack[0].index==first) return (original+Opens[stack[0].c],"missing outer closer");
        int end=text.Length; while(end>0 && Regex.IsMatch(text[end-1].ToString(),"^["+Ws+"]$")) end--;
        if (stack.Count==0 && unmatched.Count==1 && unmatched[0].index==end-1) return (Opens.Single(p=>p.Value==unmatched[0].c).Key+original,"missing outer opener");
        if (stack.Count>0 || unmatched.Count>0) throw new InvalidOperationException("Unbalanced inner grouping cannot be safely recovered");
        return (original,null);
    }
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
        GrammarTree tree;
        try { tree=ParseGrammar("intent",text,options); }
        catch(InvalidOperationException)
        {
            var repaired=RepairOuterWrapper(text,options);
            if(repaired.repair is null) throw;
            text=repaired.text;
            tree=ParseGrammar("intent",text,options);
            diagnostics.Add(new JsonObject(){["code"]="OUTER_GROUP_RECOVERED",["detail"]=repaired.repair});
        }
        // Successful grammar parses still enforce the configured depth bound.
        RepairOuterWrapper(text,options,tree);
        List<JsonObject> OperationsIn(GrammarNode node)
        {
            List<JsonObject> result=new();
            foreach(var operation in GrammarDescendants(node).Where(n=>n.Name=="operation"))
            {
                if(result.Count>=options.MaxOperations) throw new InvalidOperationException("Operation count limit exceeded");
                result.Add(ConvertOperation(tree,operation,options));
            }
            return result;
        }
        var records=OperationsIn(tree.Root);
        void VerifyBoundaries(string source,List<JsonObject> expected)
        {
            try
            {
                var alternate=ParseSequence(LexParse(source),options);
                if(JsonSerializer.Serialize(alternate)!=JsonSerializer.Serialize(expected)) throw new InvalidOperationException("Ambiguous complete operation interpretations");
            }
            catch(Exception e) when((e is InvalidOperationException or JsonException or ArgumentException) && !e.Message.Contains("limit exceeded") && !e.Message.Contains("Ambiguous")) { }
        }
        foreach(var node in GrammarDescendants(tree.Root).Where(n=>n.Name=="op_list"))
        {
            if(!GrammarDescendants(node).Any(n=>n.Name.StartsWith("line_",StringComparison.Ordinal)))
            {
                VerifyBoundaries(GrammarText(tree,node),OperationsIn(node));
                continue;
            }
            // Explicit line operations and groups delimit generic runs. Never
            // re-tokenize opaque text while proving generic newline boundaries.
            List<GrammarNode> run=new();
            void Flush()
            {
                if(run.Count==0) return;
                string source=tree.Text[tree.Tokens[run[0].Start].Start..tree.Tokens[run[^1].End-1].End];
                VerifyBoundaries(source,run.Select(n=>ConvertOperation(tree,n,options)).ToList());
                run.Clear();
            }
            Stack<GrammarNode> pending=new(); pending.Push(node);
            while(pending.Count>0)
            {
                var current=pending.Pop();
                if(current.Name=="op_group") { Flush(); continue; }
                if(current.Name=="operation")
                {
                    if(GrammarDescendants(current).Any(n=>n.Name is "line_write" or "line_remove" or "line_transfer")) Flush();
                    else run.Add(current);
                    continue;
                }
                for(int i=current.Children.Count-1;i>=0;i--) pending.Push(current.Children[i]);
            }
            Flush();
        }
        return new JsonObject(){["operations"]=new JsonArray(records.Select(x=>(JsonNode)x).ToArray()),["diagnostics"]=diagnostics};
    }

    public static JsonArray NormalizeIntent(string text,JsonNode? document,IntentOptions? options=null)
        => ConvertIntent(ParseIntent(text,options),document,options);
}
