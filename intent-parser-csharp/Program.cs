using System.Text.Json;
using System.Text.Json.Nodes;
using Csc592.IntentParser;

try
{
    if(args.Length==0)
    {
        Console.Error.WriteLine("Usage: dotnet run -- [check|replay] fixtures.json [--json-patch], or --json-lines");
        return 2;
    }
    if(args[0]=="self-test")
    {
        var result=SelfTests.Run(); Console.WriteLine(result.ToJsonString()); return result["failed"]!.GetValue<int>()>0?1:0;
    }
    if(args[0]=="--json-lines")
    {
        string? line;
        while((line=Console.ReadLine()) is not null)
        {
            try
            {
                var request=JsonNode.Parse(line)!.AsObject();
                IntentOptions options=ReadOptions(request["options"]);
                string action=request["action"]?.GetValue<string>()??"normalize";
                JsonNode? output=action switch
                {
                    "parse"=>IntentParser.ParseIntent(request["text"]!.GetValue<string>(),options),
                    "diagnostics"=>IntentParser.ParseIntentWithDiagnostics(request["text"]!.GetValue<string>(),options),
                    "normalize"=>IntentParser.NormalizeIntent(request["text"]!.GetValue<string>(),request["input"],options),
                    "convert"=>IntentParser.ConvertIntent(request["ir"]!.AsArray(),request["input"],options),
                    "apply"=>IntentParser.ApplyPatch(request["input"],request["patch"]!.AsArray(),options),
                    "prompt"=>JsonValue.Create(IntentParser.BuildPrompt(request["request"]!.GetValue<string>(),request["input"],options.IdKey)),
                    "replay"=>IntentParser.ReplayPrepared(request["records"]!.AsArray(),options),
                    _=>throw new InvalidOperationException("Unknown action")
                };
                Console.WriteLine(new JsonObject(){["ok"]=true,["result"]=output}.ToJsonString());
            }
            catch(Exception e) { Console.WriteLine(new JsonObject(){["ok"]=false,["error"]=e.Message}.ToJsonString()); }
        }
        return 0;
    }
    bool check=args[0]=="check";
    string file=args[0] is "check" or "replay"?args[1]:args[0];
    var records=JsonNode.Parse(File.ReadAllText(file))!.AsArray();
    if(!check)
    {
        Console.WriteLine(IntentParser.ReplayPrepared(records,new IntentOptions(JsonPatch:args.Contains("--json-patch"))).ToJsonString(new JsonSerializerOptions(){WriteIndented=true}));
        return 0;
    }
    int passed=0,failed=0;
    foreach(var raw in records)
    {
        var record=raw!.AsObject(); string text=record["text"]?.GetValue<string>()??record["output"]!.GetValue<string>();
        string name=record["name"]?.GetValue<string>()??"unnamed";
        try
        {
            var input=record["input"]; var before=input?.ToJsonString();
            var options=ReadOptions(record["options"]);
            var ir=IntentParser.ParseIntent(text,options);
            var custom=IntentParser.NormalizeIntent(text,input,options with {JsonPatch=false});
            var standard=IntentParser.NormalizeIntent(text,input,options with {JsonPatch=true});
            var final=IntentParser.ApplyPatch(input,custom,options);
            if(record["reject"]?.GetValue<bool>()==true) throw new Exception("Accepted expected rejection");
            foreach(var (key,actual) in new (string,JsonNode?)[]{("ir",ir),("custom",custom),("standard",standard),("expected",final)})
                if(record.ContainsKey(key) && !JsonNode.DeepEquals(record[key],actual)) throw new Exception(key+" mismatch: "+actual?.ToJsonString());
            if(before!=input?.ToJsonString()) throw new Exception("Mutated input");
            var rfcState=ApplyRfc(input,standard);
            if(!JsonNode.DeepEquals(final,rfcState)) throw new Exception("Independent RFC6902 application mismatch");
            passed++;
        }
        catch(Exception e)
        {
            if(record["reject"]?.GetValue<bool>()==true && e.Message!="Accepted expected rejection") passed++;
            else { failed++; if(failed<=30) Console.Error.WriteLine($"FAIL {name} {JsonSerializer.Serialize(text)}: {e.Message}"); }
        }
    }
    Console.WriteLine(new JsonObject(){["file"]=file,["passed"]=passed,["failed"]=failed,["mode"]="offline-native-csharp-parity"}.ToJsonString());
    return failed>0?1:0;
}
catch(Exception e) { Console.Error.WriteLine(e.Message); return 1; }

static IntentOptions ReadOptions(JsonNode? node)
    => new(JsonPatch:node?["json_patch"]?.GetValue<bool>()??false, IdKey:node?["idKey"]?.GetValue<string>()??"id",
        MaxChars:node?["maxChars"]?.GetValue<int>()??65536, MaxDepth:node?["maxDepth"]?.GetValue<int>()??64,
        MaxOperations:node?["maxOperations"]?.GetValue<int>()??256, MaxBoundaryAttempts:node?["maxBoundaryAttempts"]?.GetValue<int>()??4096,
        PathSyntax:node?["pathSyntax"]?.GetValue<string>());

// Independent, index-addressed RFC6902 reference interpreter for emitted add/replace/remove.
static JsonNode? ApplyRfc(JsonNode? input,JsonArray patch)
{
    var state=input?.DeepClone();
    foreach(var item in patch)
    {
        var op=item!.AsObject(); var pointer=op["path"]!.GetValue<string>();
        var parts=pointer[1..].Split('/').Select(p=>p.Replace("~1","/").Replace("~0","~")).ToArray();
        JsonNode? parent=state;
        foreach(string part in parts[..^1]) parent=parent is JsonArray array?array[int.Parse(part)]:parent![part];
        string key=parts[^1], action=op["op"]!.GetValue<string>();
        if(parent is JsonArray list)
        {
            int index=key=="-"?list.Count:int.Parse(key);
            if(action=="add") list.Insert(index,op["value"]?.DeepClone());
            else if(action=="replace") list[index]=op["value"]?.DeepClone();
            else if(action=="remove") list.RemoveAt(index);
            else throw new Exception("Unsupported reference operation");
        }
        else if(parent is JsonObject obj)
        {
            if(action=="remove") obj.Remove(key); else obj[key]=op["value"]?.DeepClone();
        }
        else throw new Exception("Reference pointer has no parent");
    }
    return state;
}
