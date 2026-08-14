const ts = require('typescript');
const fs = require('fs');

function main() {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.log("Usage: node js_modernizer.js <command> <filepath>");
        process.exit(1);
    }

    const command = args[0].toLowerCase();
    const filePath = args[1];

    if (!fs.existsSync(filePath)) {
        console.log(`Error: File not found: ${filePath}`);
        process.exit(2);
    }

    try {
        const origContent = fs.readFileSync(filePath, 'utf8');
        // Parse source file using typescript compiler AST parser
        const sourceFile = ts.createSourceFile(
            filePath,
            origContent,
            ts.ScriptTarget.Latest,
            true,
            filePath.endsWith('.ts') || filePath.endsWith('.tsx') ? ts.ScriptKind.TS : ts.ScriptKind.JS
        );

        let newContent = origContent;
        if (command === 'js-esm') {
            newContent = convertToEsm(sourceFile);
        } else if (command === 'js-optional-chaining') {
            newContent = addOptionalChaining(sourceFile);
        } else if (command === 'ts-no-any') {
            newContent = removeAny(sourceFile);
        } else {
            console.log(`Error: Unknown command: ${command}`);
            process.exit(3);
        }

        if (newContent !== origContent) {
            fs.writeFileSync(filePath, newContent, 'utf8');
            console.log("MODIFIED");
        } else {
            console.log("UNCHANGED");
        }
        process.exit(0);
    } catch (ex) {
        console.log(`ERROR: ${ex.message}`);
        process.exit(4);
    }
}

function convertToEsm(sourceFile) {
    const transformer = (context) => {
        return (rootNode) => {
            const visitor = (node) => {
                // const x = require('lib')
                if (ts.isVariableStatement(node)) {
                    const declarations = node.declarationList.declarations;
                    if (declarations.length === 1) {
                        const decl = declarations[0];
                        if (decl.initializer && ts.isCallExpression(decl.initializer)) {
                            const call = decl.initializer;
                            if (ts.isIdentifier(call.expression) && call.expression.text === 'require') {
                                const arg = call.arguments[0];
                                if (arg && ts.isStringLiteral(arg)) {
                                    const lib = arg.text;
                                    if (ts.isObjectBindingPattern(decl.name)) {
                                        const imports = decl.name.elements.map(el => el.name.text);
                                        const importClause = ts.factory.createImportClause(
                                            false,
                                            undefined,
                                            ts.factory.createNamedImports(
                                                imports.map(name => ts.factory.createImportSpecifier(false, undefined, ts.factory.createIdentifier(name)))
                                            )
                                        );
                                        return ts.factory.createImportDeclaration(
                                            undefined,
                                            importClause,
                                            ts.factory.createStringLiteral(lib)
                                        );
                                    }
                                    if (ts.isIdentifier(decl.name)) {
                                        const importClause = ts.factory.createImportClause(
                                            false,
                                            ts.factory.createIdentifier(decl.name.text),
                                            undefined
                                        );
                                        return ts.factory.createImportDeclaration(
                                            undefined,
                                            importClause,
                                            ts.factory.createStringLiteral(lib)
                                        );
                                    }
                                }
                            }
                        }
                    }
                }

                // module.exports = x  /  module.exports.x = y  /  exports.x = y
                if (ts.isExpressionStatement(node) && ts.isBinaryExpression(node.expression)) {
                    const expr = node.expression;
                    if (expr.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
                        if (ts.isPropertyAccessExpression(expr.left)) {
                            const left = expr.left;
                            if (ts.isIdentifier(left.expression) && left.expression.text === 'module' && left.name.text === 'exports') {
                                return ts.factory.createExportAssignment(
                                    undefined,
                                    undefined,
                                    expr.right
                                );
                            }
                            if (ts.isIdentifier(left.expression) && left.expression.text === 'exports') {
                                return ts.factory.createVariableStatement(
                                    [ts.factory.createToken(ts.SyntaxKind.ExportKeyword)],
                                    ts.factory.createVariableDeclarationList(
                                        [ts.factory.createVariableDeclaration(
                                            ts.factory.createIdentifier(left.name.text),
                                            undefined,
                                            undefined,
                                            expr.right
                                        )],
                                        ts.NodeFlags.Const
                                    )
                                );
                            }
                        }
                    }
                }

                return ts.visitEachChild(node, visitor, context);
            };
            return ts.visitNode(rootNode, visitor);
        };
    };
    const result = ts.transform(sourceFile, [transformer]);
    const printer = ts.createPrinter();
    return printer.printFile(result.transformed[0]);
}

function addOptionalChaining(sourceFile) {
    const transformer = (context) => {
        return (rootNode) => {
            const visitor = (node) => {
                if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
                    const left = node.left;
                    const right = node.right;

                    let targetName = null;
                    if (ts.isIdentifier(left)) {
                        targetName = left.text;
                    } else if (ts.isBinaryExpression(left)) {
                        if (left.operatorToken.kind === ts.SyntaxKind.ExclamationEqualsToken || left.operatorToken.kind === ts.SyntaxKind.ExclamationEqualsEqualsToken) {
                            if (ts.isIdentifier(left.left) && (left.right.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(left.right) && left.right.text === 'undefined'))) {
                                targetName = left.left.text;
                            }
                        }
                    }

                    if (targetName && ts.isPropertyAccessExpression(right)) {
                        if (ts.isIdentifier(right.expression) && right.expression.text === targetName) {
                            return ts.factory.createPropertyAccessChain(
                                ts.factory.createIdentifier(targetName),
                                ts.factory.createToken(ts.SyntaxKind.QuestionDotToken),
                                right.name
                            );
                        }
                    }
                }
                return ts.visitEachChild(node, visitor, context);
            };
            return ts.visitNode(rootNode, visitor);
        };
    };
    const result = ts.transform(sourceFile, [transformer]);
    const printer = ts.createPrinter();
    return printer.printFile(result.transformed[0]);
}

function removeAny(sourceFile) {
    const transformer = (context) => {
        return (rootNode) => {
            const visitor = (node) => {
                if (node.kind === ts.SyntaxKind.AnyKeyword) {
                    return ts.factory.createKeywordTypeNode(ts.SyntaxKind.UnknownKeyword);
                }
                return ts.visitEachChild(node, visitor, context);
            };
            return ts.visitNode(rootNode, visitor);
        };
    };
    const result = ts.transform(sourceFile, [transformer]);
    const printer = ts.createPrinter();
    return printer.printFile(result.transformed[0]);
}

main();
