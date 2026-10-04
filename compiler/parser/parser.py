"""Recursive-descent parser for the Devara compiler."""

from __future__ import annotations

from compiler.ast.nodes import (
    ArrayAccess,
    Assignment,
    AssignmentUpdate,
    BinaryExpression,
    BinaryOp,
    Block,
    BreakStatement,
    CastExpression,
    ContinueStatement,
    Declaration,
    DecrementUpdate,
    Expression,
    ExpressionStatement,
    ForInit,
    ForLoop,
    ForUpdate,
    FunctionCall,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    IncrementUpdate,
    Input,
    Literal,
    LiteralType,
    Output,
    Parameter,
    PrimitiveType,
    Program,
    RangeLoop,
    ReturnStatement,
    Statement,
    Type,
    UnaryExpression,
    UnaryOp,
    UnaryPosition,
    WhileLoop,
)
from compiler.lexer.tokens import Token, TokenType
from compiler.parser.errors import ParserError

# ── Type Mapping ──

_TYPE_MAP = {
    TokenType.INT: PrimitiveType.INT,
    TokenType.FLOAT: PrimitiveType.FLOAT,
    TokenType.BOOL: PrimitiveType.BOOL,
    TokenType.CHAR: PrimitiveType.CHAR,
    TokenType.PADHAM: PrimitiveType.PADHAM,
    TokenType.VOID: PrimitiveType.VOID,
}


class Parser:
    """Recursive-descent parser that produces a typed AST."""

    def __init__(self, tokens: list[Token], filename: str = "<stdin>") -> None:
        self.tokens = tokens
        self.filename = filename
        self.current = 0
        self.errors: list[ParserError] = []

    # ── Public API ──

    def parse(self) -> Program:
        """Parse the entire token stream into a Program node."""
        items = []
        while not self.is_at_end():
            try:
                item = self.parse_top_level_item()
                if item is not None:
                    items.append(item)
            except ParserError:
                self.synchronize_top_level()

        start_line = 1 if not items else items[0].line
        start_col = 1 if not items else items[0].column
        end_line = 1 if not items else (items[-1].end_line or items[-1].line)
        end_col = 1 if not items else (items[-1].end_column or items[-1].column)
        return Program(
            line=start_line,
            column=start_col,
            end_line=end_line,
            end_column=end_col,
            items=items,
        )

    # ── Token Navigation ──

    def peek(self) -> Token:
        return self.tokens[self.current]

    def peek_next(self) -> Token:
        if self.current + 1 >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.current + 1]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def check(self, token_type: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == token_type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def match(self, *types: TokenType) -> bool:
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def consume(self, token_type: TokenType, message: str) -> Token:
        if self.check(token_type):
            return self.advance()
        raise self.error(self.peek(), message)

    # ── Error Handling ──

    def error(self, token: Token, message: str) -> ParserError:
        err = ParserError(message, token.line, token.column, self.filename)
        self.errors.append(err)
        return err

    def synchronize_top_level(self) -> None:
        """Panic mode recovery at top-level."""
        self.advance()
        while not self.is_at_end():
            if self.previous().type in (TokenType.SEMICOLON, TokenType.RBRACE):
                return
            if self.peek().type in (
                TokenType.INT,
                TokenType.FLOAT,
                TokenType.BOOL,
                TokenType.CHAR,
                TokenType.PADHAM,
                TokenType.VOID,
                TokenType.IDENTIFIER,
                TokenType.INT_LITERAL,
                TokenType.FLOAT_LITERAL,
                TokenType.CHAR_LITERAL,
                TokenType.STRING_LITERAL,
                TokenType.NIJAM,
                TokenType.ABADDHAM,
            ):
                return
            self.advance()

    def synchronize_statement(self) -> None:
        """Panic mode recovery at statement level."""
        self.advance()
        while not self.is_at_end():
            if self.previous().type in (TokenType.SEMICOLON, TokenType.RBRACE):
                return
            if self.peek().type in (
                TokenType.INT,
                TokenType.FLOAT,
                TokenType.BOOL,
                TokenType.CHAR,
                TokenType.PADHAM,
                TokenType.VOID,
                TokenType.PRATISARI,
                TokenType.PRATI,
                TokenType.AAPU,
                TokenType.SAAGU,
                TokenType.LBRACE,
                TokenType.IDENTIFIER,
                TokenType.INT_LITERAL,
                TokenType.FLOAT_LITERAL,
                TokenType.CHAR_LITERAL,
                TokenType.STRING_LITERAL,
                TokenType.NIJAM,
                TokenType.ABADDHAM,
            ):
                return
            self.advance()

    # ── Top Level ──

    def parse_top_level_item(self) -> FunctionDeclaration | Statement | None:
        if self.peek().type in _TYPE_MAP:
            # Look ahead: Type IDENTIFIER [maybe brackets] CHARYA -> Function
            lookahead = self.current + 2
            while lookahead < len(self.tokens) and self.tokens[lookahead].type in (
                TokenType.LBRACKET,
                TokenType.RBRACKET,
                TokenType.INT_LITERAL,
                TokenType.IDENTIFIER,
                TokenType.PLUS,
                TokenType.MINUS,
                TokenType.STAR,
                TokenType.SLASH,
                TokenType.PERCENT,
                TokenType.LPAREN,
                TokenType.RPAREN,
            ):
                lookahead += 1
            
            if lookahead < len(self.tokens) and self.tokens[lookahead].type == TokenType.CHARYA:
                return self.parse_function_declaration()
            
            return self.parse_declaration()
            
        return self.parse_statement()

    def parse_function_declaration(self) -> FunctionDeclaration:
        start_token = self.peek()
        ret_type = self.parse_type()
        name = self.consume(TokenType.IDENTIFIER, "Expected function name.").lexeme
        self.consume(TokenType.CHARYA, "Expected 'charya' after function name.")
        
        self.consume(TokenType.LPAREN, "Expected '(' after 'charya'.")
        parameters = []
        if not self.check(TokenType.RPAREN):
            while True:
                param_type = self.parse_type()
                param_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name.")
                end_tok = param_name
                
                if self.match(TokenType.LBRACKET):
                    rbracket = self.consume(TokenType.RBRACKET, "Expected ']' after '[' in array parameter.")
                    end_tok = rbracket
                    param_type = Type(
                        line=param_type.line,
                        column=param_type.column,
                        end_line=end_tok.line,
                        end_column=end_tok.column,
                        name=param_type.name,
                        array_dimensions=[None],
                    )
                    
                parameters.append(
                    Parameter(
                        line=param_type.line,
                        column=param_type.column,
                        end_line=end_tok.line,
                        end_column=end_tok.column,
                        type=param_type,
                        name=param_name.lexeme,
                    )
                )
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RPAREN, "Expected ')' after parameters.")
        
        body = self.parse_block()
        return FunctionDeclaration(
            line=start_token.line,
            column=start_token.column,
            end_line=body.end_line or body.line,
            end_column=body.end_column or body.column,
            return_type=ret_type,
            name=name,
            parameters=parameters,
            body=body,
        )

    # ── Statements ──

    def parse_statement(self) -> Statement | None:
        try:
            if self.peek().type in _TYPE_MAP:
                return self.parse_declaration()
            if self.match(TokenType.PRATISARI):
                return self.parse_for_loop()
            if self.match(TokenType.PRATI):
                return self.parse_range_loop()
            if self.match(TokenType.AAPU):
                start = self.previous()
                return BreakStatement(line=start.line, column=start.column, end_line=start.line, end_column=start.column)
            if self.match(TokenType.SAAGU):
                start = self.previous()
                return ContinueStatement(line=start.line, column=start.column, end_line=start.line, end_column=start.column)
            if self.match(TokenType.LBRACE):
                return self.parse_block()
                
            return self.parse_expression_statement()
        except ParserError:
            self.synchronize_statement()
            return None

    def parse_declaration(self) -> Declaration:
        start_token = self.peek()
        decl_type = self.parse_type()
        name = self.consume(TokenType.IDENTIFIER, "Expected variable name after type.")
        end_tok = name
        
        dimensions = []
        while self.match(TokenType.LBRACKET):
            dim_expr = self.parse_expression()
            end_tok = self.consume(TokenType.RBRACKET, "Expected ']' after array dimension.")
            dimensions.append(dim_expr)
            
        if dimensions:
            decl_type = Type(
                line=decl_type.line,
                column=decl_type.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                name=decl_type.name,
                array_dimensions=dimensions,
            )
            
        return Declaration(
            line=start_token.line,
            column=start_token.column,
            end_line=end_tok.line,
            end_column=end_tok.column,
            type=decl_type,
            name=name.lexeme,
        )

    def parse_type(self) -> Type:
        start = self.peek()
        if start.type not in _TYPE_MAP:
            raise self.error(start, "Expected type keyword.")
        
        primitive = _TYPE_MAP[start.type]
        self.advance()
            
        return Type(
            line=start.line,
            column=start.column,
            end_line=start.line,
            end_column=start.column,
            name=primitive,
            array_dimensions=[],
        )

    def parse_block(self) -> Block:
        if self.previous().type != TokenType.LBRACE:
            start = self.consume(TokenType.LBRACE, "Expected '{'.")
        else:
            start = self.previous()
            
        statements = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            item = self.parse_statement()
            if item is not None:
                statements.append(item)
            
        rbrace = self.consume(TokenType.RBRACE, "Expected '}' after block.")
        return Block(
            line=start.line,
            column=start.column,
            end_line=rbrace.line,
            end_column=rbrace.column,
            statements=statements,
        )

    def parse_expression_statement(self) -> Statement:
        expr = self.parse_expression()
        
        if self.match(TokenType.LO):
            if not isinstance(expr, (Identifier, ArrayAccess)):
                raise self.error(self.previous(), "Expected identifier or array access as assignment target.")
            value = self.parse_expression()
            self.consume(TokenType.PETTU, "Expected 'pettu' after assignment value.")
            end_tok = self.previous()
            return Assignment(
                line=expr.line,
                column=expr.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=expr,
                value=value,
            )
            
        if self.match(TokenType.NI):
            if self.match(TokenType.CHADUVU):
                if not isinstance(expr, (Identifier, ArrayAccess)):
                    raise self.error(self.previous(), "Expected identifier or array access for input.")
                end_tok = self.previous()
                return Input(
                    line=expr.line,
                    column=expr.column,
                    end_line=end_tok.line,
                    end_column=end_tok.column,
                    target=expr,
                )
            elif self.match(TokenType.CHUPI):
                end_tok = self.previous()
                return Output(
                    line=expr.line,
                    column=expr.column,
                    end_line=end_tok.line,
                    end_column=end_tok.column,
                    value=expr,
                )
            else:
                raise self.error(self.peek(), "Expected 'chaduvu' or 'chupi' after 'ni'.")
                
        if self.match(TokenType.AYITE):
            then_block = self.parse_block()
            else_block = None
            if self.match(TokenType.LEKUNTE):
                if self.check(TokenType.LBRACE):
                    else_block = self.parse_block()
                else:
                    start_tok = self.peek()
                    else_stmt = self.parse_expression_statement()
                    if not isinstance(else_stmt, IfStatement):
                        raise self.error(start_tok, "Expected '{' or if-statement after 'lekunte'.")
                    else_block = else_stmt
            end_line = (else_block.end_line or else_block.line) if else_block else (then_block.end_line or then_block.line)
            end_column = (else_block.end_column or else_block.column) if else_block else (then_block.end_column or then_block.column)
            return IfStatement(
                line=expr.line,
                column=expr.column,
                end_line=end_line,
                end_column=end_column,
                condition=expr,
                then_block=then_block,
                else_block=else_block,
            )
            
        if self.match(TokenType.UNNANTA):
            self.consume(TokenType.VARAKU, "Expected 'varaku' after 'unnanta'.")
            body = self.parse_block()
            return WhileLoop(
                line=expr.line,
                column=expr.column,
                end_line=body.end_line or body.line,
                end_column=body.end_column or body.column,
                condition=expr,
                body=body,
            )
            
        if self.match(TokenType.IVVU):
            end_tok = self.previous()
            return ReturnStatement(
                line=expr.line,
                column=expr.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                value=expr,
            )
            
        if isinstance(expr, FunctionCall):
            return ExpressionStatement(
                line=expr.line,
                column=expr.column,
                end_line=expr.end_line or expr.line,
                end_column=expr.end_column or expr.column,
                expression=expr,
            )
            
        raise self.error(self.peek(), "Expected statement keyword after expression.")

    def parse_for_loop(self) -> ForLoop:
        start = self.previous()
        self.consume(TokenType.LPAREN, "Expected '(' after 'pratisari'.")
        
        # Init (mandatory according to canonical grammar)
        if self.check(TokenType.SEMICOLON):
            raise self.error(self.peek(), "Expected loop initialization in pratisari.")
            
        if self.peek().type in _TYPE_MAP:
            type_node = self.parse_type()
            target_tok = self.consume(TokenType.IDENTIFIER, "Expected loop variable in pratisari.")
            target_expr = Identifier(
                line=target_tok.line,
                column=target_tok.column,
                end_line=target_tok.line,
                end_column=target_tok.column,
                name=target_tok.lexeme,
            )
            val_expr = None
            if self.match(TokenType.LO):
                val_expr = self.parse_expression()
                self.consume(TokenType.PETTU, "Expected 'pettu' in pratisari init.")
            end_tok = self.previous()
            init = ForInit(
                line=type_node.line,
                column=type_node.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=target_expr,
                value=val_expr,
                type=type_node,
            )
        elif self.check(TokenType.IDENTIFIER) and self.peek_next().type == TokenType.LO:
            target_tok = self.advance()
            target_expr = Identifier(
                line=target_tok.line,
                column=target_tok.column,
                end_line=target_tok.line,
                end_column=target_tok.column,
                name=target_tok.lexeme,
            )
            self.consume(TokenType.LO, "Expected 'lo' in pratisari init.")
            val_expr = self.parse_expression()
            self.consume(TokenType.PETTU, "Expected 'pettu' in pratisari init.")
            end_tok = self.previous()
            init = ForInit(
                line=target_tok.line,
                column=target_tok.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=target_expr,
                value=val_expr,
                type=None,
            )
        elif self.check(TokenType.IDENTIFIER):
            target_tok = self.advance()
            target_expr = Identifier(
                line=target_tok.line,
                column=target_tok.column,
                end_line=target_tok.line,
                end_column=target_tok.column,
                name=target_tok.lexeme,
            )
            start_expr = self.parse_expression()
            self.consume(TokenType.THO, "Expected 'tho' in pratisari init.")
            self.consume(TokenType.MODHALU, "Expected 'modhalu' in pratisari init.")
            end_tok = self.previous()
            init = ForInit(
                line=target_tok.line,
                column=target_tok.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=target_expr,
                value=start_expr,
                type=None,
            )
        else:
            raise self.error(self.peek(), "Expected loop initialization in pratisari.")
            
        self.consume(TokenType.SEMICOLON, "Expected ';' after pratisari init.")
        
        # Condition (mandatory according to canonical grammar)
        if self.check(TokenType.SEMICOLON):
            raise self.error(self.peek(), "Expected condition in pratisari.")
        condition = self.parse_expression()
        if self.match(TokenType.UNNANTA):
            raise self.error(self.previous(), "'unnanta varaku' is not allowed in a pratisari loop condition.")
        self.consume(TokenType.SEMICOLON, "Expected ';' after pratisari condition.")
        
        # Update (mandatory according to canonical grammar)
        if self.check(TokenType.RPAREN):
            raise self.error(self.peek(), "Expected update in pratisari.")
        update = self.parse_for_update()
        self.consume(TokenType.RPAREN, "Expected ')' after pratisari.")
        
        body = self.parse_block()
        return ForLoop(
            line=start.line,
            column=start.column,
            end_line=body.end_line or body.line,
            end_column=body.end_column or body.column,
            init=init,
            condition=condition,
            update=update,
            body=body,
        )

    def parse_for_update(self) -> ForUpdate:
        if self.match(TokenType.INCREMENT):
            start = self.previous()
            target = self.parse_primary()
            if not isinstance(target, (Identifier, ArrayAccess)):
                raise self.error(self.previous(), "Expected identifier or array access for increment target.")
            return IncrementUpdate(
                line=start.line,
                column=start.column,
                end_line=target.end_line or target.line,
                end_column=target.end_column or target.column,
                target=target,
                prefix=True,
            )
        if self.match(TokenType.DECREMENT):
            start = self.previous()
            target = self.parse_primary()
            if not isinstance(target, (Identifier, ArrayAccess)):
                raise self.error(self.previous(), "Expected identifier or array access for decrement target.")
            return DecrementUpdate(
                line=start.line,
                column=start.column,
                end_line=target.end_line or target.line,
                end_column=target.end_column or target.column,
                target=target,
                prefix=True,
            )
            
        expr = self.parse_expression()
        
        if self.match(TokenType.INCREMENT):
            end_tok = self.previous()
            if not isinstance(expr, (Identifier, ArrayAccess)):
                raise self.error(self.previous(), "Expected identifier or array access for increment target.")
            return IncrementUpdate(
                line=expr.line,
                column=expr.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=expr,
                prefix=False,
            )
        if self.match(TokenType.DECREMENT):
            end_tok = self.previous()
            if not isinstance(expr, (Identifier, ArrayAccess)):
                raise self.error(self.previous(), "Expected identifier or array access for decrement target.")
            return DecrementUpdate(
                line=expr.line,
                column=expr.column,
                end_line=end_tok.line,
                end_column=end_tok.column,
                target=expr,
                prefix=False,
            )
            
        self.consume(TokenType.LO, "Expected 'lo' in pratisari update.")
        val_expr = self.parse_expression()
        self.consume(TokenType.PETTU, "Expected 'pettu' in pratisari update.")
        end_tok = self.previous()
        if not isinstance(expr, (Identifier, ArrayAccess)):
            raise self.error(self.previous(), "Expected identifier or array access as assignment target.")
        return AssignmentUpdate(
            line=expr.line,
            column=expr.column,
            end_line=end_tok.line,
            end_column=end_tok.column,
            target=expr,
            value=val_expr,
        )

    def parse_range_loop(self) -> RangeLoop:
        start = self.previous()
        target = self.consume(TokenType.IDENTIFIER, "Expected variable name after 'prati'.").lexeme
        start_expr = self.parse_expression()
        self.consume(TokenType.NUNDI, "Expected 'nundi' after start expression.")
        end_expr = self.parse_expression()
        self.consume(TokenType.VARAKU, "Expected 'varaku' after end expression.")
        body = self.parse_block()
        
        return RangeLoop(
            line=start.line,
            column=start.column,
            end_line=body.end_line or body.line,
            end_column=body.end_column or body.column,
            target=target,
            start=start_expr,
            end=end_expr,
            body=body,
        )

    # ── Expressions ──

    def parse_expression(self) -> Expression:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expression:
        expr = self.parse_logical_and()
        while self.match(TokenType.OR):
            op_token = self.previous()
            right = self.parse_logical_and()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=BinaryOp.OR,
                left=expr,
                right=right,
            )
        return expr

    def parse_logical_and(self) -> Expression:
        expr = self.parse_equality()
        while self.match(TokenType.AND):
            op_token = self.previous()
            right = self.parse_equality()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=BinaryOp.AND,
                left=expr,
                right=right,
            )
        return expr

    def parse_equality(self) -> Expression:
        expr = self.parse_relational()
        while self.match(TokenType.EQEQ, TokenType.NEQ):
            op_token = self.previous()
            op = BinaryOp.EQ if op_token.type == TokenType.EQEQ else BinaryOp.NE
            right = self.parse_relational()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=op,
                left=expr,
                right=right,
            )
        return expr

    def parse_relational(self) -> Expression:
        expr = self.parse_additive()
        while self.match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op_token = self.previous()
            if op_token.type == TokenType.LT:
                op = BinaryOp.LT
            elif op_token.type == TokenType.GT:
                op = BinaryOp.GT
            elif op_token.type == TokenType.LTE:
                op = BinaryOp.LE
            else:
                op = BinaryOp.GE
                
            right = self.parse_additive()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=op,
                left=expr,
                right=right,
            )
        return expr

    def parse_additive(self) -> Expression:
        expr = self.parse_multiplicative()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op_token = self.previous()
            op = BinaryOp.ADD if op_token.type == TokenType.PLUS else BinaryOp.SUB
            right = self.parse_multiplicative()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=op,
                left=expr,
                right=right,
            )
        return expr

    def parse_multiplicative(self) -> Expression:
        expr = self.parse_unary()
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_token = self.previous()
            if op_token.type == TokenType.STAR:
                op = BinaryOp.MUL
            elif op_token.type == TokenType.SLASH:
                op = BinaryOp.DIV
            else:
                op = BinaryOp.MOD
                
            right = self.parse_unary()
            expr = BinaryExpression(
                line=expr.line,
                column=expr.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=op,
                left=expr,
                right=right,
            )
        return expr

    def parse_unary(self) -> Expression:
        if self.check(TokenType.LPAREN) and self.peek_next().type in _TYPE_MAP:
            start_tok = self.advance()
            type_node = self.parse_type()
            self.consume(TokenType.RPAREN, "Expected ')' after type in cast.")
            operand = self.parse_unary()
            return CastExpression(
                line=start_tok.line,
                column=start_tok.column,
                end_line=operand.end_line or operand.line,
                end_column=operand.end_column or operand.column,
                target_type=type_node,
                expression=operand,
            )

        if self.match(TokenType.NOT, TokenType.PLUS, TokenType.MINUS):
            op_token = self.previous()
            if op_token.type == TokenType.NOT:
                op = UnaryOp.NOT
            elif op_token.type == TokenType.PLUS:
                op = UnaryOp.POSITIVE
            else:
                op = UnaryOp.NEGATE
                
            right = self.parse_unary()
            return UnaryExpression(
                line=op_token.line,
                column=op_token.column,
                end_line=right.end_line or right.line,
                end_column=right.end_column or right.column,
                operator=op,
                operand=right,
                position=UnaryPosition.PREFIX,
            )
            
        return self.parse_primary()

    def parse_primary(self) -> Expression:
        if self.match(TokenType.INT_LITERAL):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.INTEGER, end_line=tok.line, end_column=tok.column)
        if self.match(TokenType.FLOAT_LITERAL):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.FLOAT, end_line=tok.line, end_column=tok.column)
        if self.match(TokenType.CHAR_LITERAL):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.CHAR, end_line=tok.line, end_column=tok.column)
        if self.match(TokenType.STRING_LITERAL):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.STRING, end_line=tok.line, end_column=tok.column)
        if self.match(TokenType.NIJAM):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.BOOL, end_line=tok.line, end_column=tok.column)
        if self.match(TokenType.ABADDHAM):
            tok = self.previous()
            return Literal(tok.line, tok.column, tok.lexeme, LiteralType.BOOL, end_line=tok.line, end_column=tok.column)
            
        if self.match(TokenType.LPAREN):
            start = self.previous()
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')' after expression.")
            return expr
            
        if self.match(TokenType.IDENTIFIER):
            start = self.previous()
            expr: Expression = Identifier(start.line, start.column, start.lexeme, end_line=start.line, end_column=start.column)
            
            # Postfix operators (Array access and Function call)
            while True:
                if self.match(TokenType.LBRACKET):
                    index = self.parse_expression()
                    rbracket = self.consume(TokenType.RBRACKET, "Expected ']' after array index.")
                    expr = ArrayAccess(expr.line, expr.column, expr, index, end_line=rbracket.line, end_column=rbracket.column)
                elif self.match(TokenType.LPAREN):
                    arguments = []
                    if not self.check(TokenType.RPAREN):
                        while True:
                            arguments.append(self.parse_expression())
                            if not self.match(TokenType.COMMA):
                                break
                    rparen = self.consume(TokenType.RPAREN, "Expected ')' after arguments.")
                    expr = FunctionCall(expr.line, expr.column, expr, arguments, end_line=rparen.line, end_column=rparen.column)
                else:
                    break
                    
            return expr
            
        raise self.error(self.peek(), "Expected expression.")
