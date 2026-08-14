using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace RoslynTool
{
    public class RequestPayload
    {
        public string WorkspacePath { get; set; } = "";
        public string RecipeId { get; set; } = "";
        public List<string> Files { get; set; } = new();
        public string TargetFramework { get; set; } = "net8.0";
        public bool DryRun { get; set; } = false;
    }

    public class ChangedFileInfo
    {
        public string FilePath { get; set; } = "";
        public string BeforeContent { get; set; } = "";
        public string AfterContent { get; set; } = "";
        public string Status { get; set; } = "UNCHANGED";
    }

    public class DiagnosticInfo
    {
        public string Severity { get; set; } = "";
        public string Message { get; set; } = "";
        public string FilePath { get; set; } = "";
        public int Line { get; set; }
        public int Column { get; set; }
    }

    public class ResponsePayload
    {
        public bool Success { get; set; } = true;
        public string ErrorMessage { get; set; } = "";
        public List<ChangedFileInfo> ChangedFiles { get; set; } = new();
        public List<DiagnosticInfo> Diagnostics { get; set; } = new();
    }

    class Program
    {
        static int Main(string[] args)
        {
            string inputJson;
            try
            {
                inputJson = Console.In.ReadToEnd();
                if (string.IsNullOrWhiteSpace(inputJson))
                {
                    var response = new ResponsePayload { Success = false, ErrorMessage = "No JSON input provided on stdin." };
                    Console.WriteLine(JsonSerializer.Serialize(response));
                    return 1;
                }
            }
            catch (Exception ex)
            {
                var response = new ResponsePayload { Success = false, ErrorMessage = $"Failed to read stdin: {ex.Message}" };
                Console.WriteLine(JsonSerializer.Serialize(response));
                return 1;
            }

            RequestPayload request;
            try
            {
                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                request = JsonSerializer.Deserialize<RequestPayload>(inputJson, options) ?? new RequestPayload();
            }
            catch (Exception ex)
            {
                var response = new ResponsePayload { Success = false, ErrorMessage = $"Failed to deserialize JSON: {ex.Message}" };
                Console.WriteLine(JsonSerializer.Serialize(response));
                return 2;
            }

            var responsePayload = new ResponsePayload();

            try
            {
                foreach (var relPath in request.Files)
                {
                    string fullPath = Path.IsPathRooted(relPath) ? relPath : Path.Combine(request.WorkspacePath, relPath);
                    if (!File.Exists(fullPath))
                    {
                        responsePayload.Diagnostics.Add(new DiagnosticInfo
                        {
                            Severity = "Warning",
                            Message = $"File not found: {relPath}",
                            FilePath = relPath
                        });
                        continue;
                    }

                    string orig = File.ReadAllText(fullPath);
                    string transformed = orig;

                    var tree = CSharpSyntaxTree.ParseText(orig);
                    var root = tree.GetRoot();

                    var coreDir = Path.GetDirectoryName(typeof(object).Assembly.Location);
                    var refs = new List<MetadataReference>();
                    if (coreDir != null)
                    {
                        foreach (var file in Directory.GetFiles(coreDir, "*.dll"))
                        {
                            try
                            {
                                refs.Add(MetadataReference.CreateFromFile(file));
                            }
                            catch { }
                        }
                    }

                    var compilation = CSharpCompilation.Create("TempAssembly")
                        .AddReferences(refs)
                        .AddSyntaxTrees(tree);

                    var semanticModel = compilation.GetSemanticModel(tree);

                    foreach (var diag in compilation.GetDiagnostics())
                    {
                        if (diag.Severity == DiagnosticSeverity.Error)
                        {
                            var lineSpan = diag.Location.GetLineSpan();
                            responsePayload.Diagnostics.Add(new DiagnosticInfo
                            {
                                Severity = diag.Severity.ToString(),
                                Message = diag.GetMessage(),
                                FilePath = relPath,
                                Line = lineSpan.StartLinePosition.Line + 1,
                                Column = lineSpan.StartLinePosition.Character + 1
                            });
                        }
                    }

                    if (request.RecipeId == "cs-file-scoped-namespace")
                    {
                        transformed = ConvertToFileScopedNamespace(root);
                    }
                    else if (request.RecipeId == "cs-var-modernization")
                    {
                        transformed = ApplyVarModernization(root, semanticModel);
                    }
                    else
                    {
                        var response = new ResponsePayload { Success = false, ErrorMessage = $"Unknown recipe: {request.RecipeId}" };
                        Console.WriteLine(JsonSerializer.Serialize(response));
                        return 3;
                    }

                    if (transformed != orig)
                    {
                        if (!request.DryRun)
                        {
                            File.WriteAllText(fullPath, transformed);
                        }
                        responsePayload.ChangedFiles.Add(new ChangedFileInfo
                        {
                            FilePath = relPath,
                            BeforeContent = orig,
                            AfterContent = transformed,
                            Status = "MODIFIED"
                        });
                    }
                    else
                    {
                        responsePayload.ChangedFiles.Add(new ChangedFileInfo
                        {
                            FilePath = relPath,
                            BeforeContent = orig,
                            AfterContent = orig,
                            Status = "UNCHANGED"
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                responsePayload.Success = false;
                responsePayload.ErrorMessage = ex.ToString();
                Console.WriteLine(JsonSerializer.Serialize(responsePayload));
                return 4;
            }

            Console.WriteLine(JsonSerializer.Serialize(responsePayload));
            return 0;
        }

        static string ConvertToFileScopedNamespace(SyntaxNode root)
        {
            var namespaces = root.DescendantNodes().OfType<NamespaceDeclarationSyntax>().ToList();
            if (namespaces.Count != 1)
            {
                return root.ToFullString();
            }

            var ns = namespaces[0];
            
            var fileScoped = SyntaxFactory.FileScopedNamespaceDeclaration(ns.Name.WithoutTrailingTrivia())
                .WithNamespaceKeyword(SyntaxFactory.Token(SyntaxKind.NamespaceKeyword).WithTrailingTrivia(SyntaxFactory.Space))
                .WithSemicolonToken(SyntaxFactory.Token(SyntaxKind.SemicolonToken).WithTrailingTrivia(SyntaxFactory.ElasticCarriageReturnLineFeed))
                .AddMembers(ns.Members.ToArray())
                .AddUsings(ns.Usings.ToArray())
                .AddExterns(ns.Externs.ToArray())
                .WithLeadingTrivia(ns.GetLeadingTrivia());

            var newRoot = root.ReplaceNode(ns, fileScoped);
            return newRoot.ToFullString();
        }

        static string ApplyVarModernization(SyntaxNode root, SemanticModel semanticModel)
        {
            var rewriter = new VarRewriter(semanticModel);
            var newRoot = rewriter.Visit(root);
            return newRoot.ToFullString();
        }
    }

    class VarRewriter : CSharpSyntaxRewriter
    {
        private readonly SemanticModel _semanticModel;

        public VarRewriter(SemanticModel semanticModel)
        {
            _semanticModel = semanticModel;
        }

        public override SyntaxNode VisitLocalDeclarationStatement(LocalDeclarationStatementSyntax node)
        {
            if (node.Declaration.Variables.Count != 1)
                return base.VisitLocalDeclarationStatement(node);

            var variable = node.Declaration.Variables[0];
            if (variable.Initializer == null)
                return base.VisitLocalDeclarationStatement(node);

            if (node.Declaration.Type.IsVar)
                return base.VisitLocalDeclarationStatement(node);

            var typeInfo = _semanticModel.GetTypeInfo(variable.Initializer.Value);
            var declaredTypeSymbol = _semanticModel.GetTypeInfo(node.Declaration.Type).Type;

            if (typeInfo.Type != null && declaredTypeSymbol != null)
            {
                if (SymbolEqualityComparer.Default.Equals(typeInfo.Type, declaredTypeSymbol))
                {
                    var varType = SyntaxFactory.IdentifierName("var")
                        .WithLeadingTrivia(node.Declaration.Type.GetLeadingTrivia())
                        .WithTrailingTrivia(node.Declaration.Type.GetTrailingTrivia());
                    
                    var newDeclaration = node.Declaration.WithType(varType);
                    return node.WithDeclaration(newDeclaration);
                }
            }

            return base.VisitLocalDeclarationStatement(node);
        }
    }
}
