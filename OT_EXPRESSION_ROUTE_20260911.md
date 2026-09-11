# Seed evaluation — no expression rewrite

Seed text is evaluated **exactly as written**.

- No AST rewrite of `+ - * / **` into `math_*`
- No rewrite of `ot_*` names into `math_*`
- No internal re-expression for same-result with IEEE

Named functions in the seed environment keep their own definitions:

| Call | OT ON | OT OFF |
|------|--------|--------|
| `math_add` / `math_mul` / … | book `ot_add` / `ot_prod` / … | ordinary arithmetic |
| `ot_add` / `ot_prod` / … | book Operations | book Operations (explicit) |
| plain `+` `*` `/` | Python operators | Python operators |

Interpretation of the OT toggle applies only where the author wrote `math_*`
(or other dual-mode helpers). Ordinary operators are never substituted.
