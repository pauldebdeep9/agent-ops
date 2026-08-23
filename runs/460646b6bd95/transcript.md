# Case S06
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 10 CS | 10 CS | 120 EA | $150.00 | $12.50 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S06",
  "supplier": "Vantage Bearings Pte Ltd",
  "currency": "USD",
  "lines": [
    {
      "line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "10",
      "uom": "CS",
      "unit_price": "150.00",
      "extended": "1500.00"
    }
  ]
}
```

**get_receipt**
```json
{
  "receipt_number": "GR-S06",
  "line_count": 1,
  "lines": [
    {
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity_received": "10",
      "uom": "CS"
    }
  ]
}
```

**get_invoice**
```json
{
  "invoice_id": "INV-S06",
  "supplier_invoice_number": "SIN-0001",
  "prior_invoice_numbers_on_this_po": [],
  "lines": [
    {
      "line_number": 1,
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "120",
      "uom": "EA",
      "unit_price": "12.50",
      "extended": "1500.00"
    }
  ]
}
```

### Turn 2
Called `compare_quantities`, `compare_prices`.

**compare_quantities**
```json
{
  "lines": [
    {
      "invoice_line": 1,
      "po_line": 1,
      "on_po": true,
      "invoiced": "120",
      "invoiced_uom": "EA",
      "ordered": "10",
      "ordered_uom": "CS",
      "received": "10",
      "uom_conversion_factor": "12"
    }
  ]
}
```

**compare_prices**
```json
{
  "lines": [
    {
      "invoice_line": 1,
      "on_po": true,
      "po_unit_price": "150.00",
      "invoiced_unit_price": "12.50",
      "delta": "-137.50",
      "po_extended": "1500.00",
      "invoiced_extended": "1500.00",
      "extended_amounts_agree": true
    }
  ]
}
```

### Turn 3
Called `write_proposal`.

**write_proposal**
```json
{
  "recorded": true,
  "disposition": "escalate",
  "exception_classes": [
    "uom_mismatch",
    "price_variance"
  ],
  "rationale": "The invoice presents a price variance issue with the invoiced unit price significantly lower than the PO unit price, despite the extended amounts agreeing. Additionally, there is a UOM mismatch as the invoice uses EA while the PO uses CS."
}
```

## The proposal

Disposition: **escalate**
Exception classes claimed: uom_mismatch, price_variance
Rationale: The invoice presents a price variance issue with the invoiced unit price significantly lower than the PO unit price, despite the extended amounts agreeing. Additionally, there is a UOM mismatch as the invoice uses EA while the PO uses CS.

## The gate verdict

**Rejected.** claimed exceptions ['price_variance', 'uom_mismatch'] do not match verified ['uom_mismatch']

## Gold

Expected disposition: **request_po_amendment**
Why: PO is in CS, invoice in EA, factor 12. Extended amounts agree exactly at 1500.00, so nothing is owed either way. The trap: this presents as 12x over-invoicing and the naive answer is a credit memo.