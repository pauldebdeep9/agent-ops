# Case S03
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 100 EA | 100 EA | $12.50 | $13.70 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S03",
  "supplier": "Vantage Bearings Pte Ltd",
  "currency": "USD",
  "lines": [
    {
      "line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "100",
      "uom": "EA",
      "unit_price": "12.50",
      "extended": "1250.00"
    }
  ]
}
```

**get_receipt**
```json
{
  "receipt_number": "GR-S03",
  "line_count": 1,
  "lines": [
    {
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity_received": "100",
      "uom": "EA"
    }
  ]
}
```

**get_invoice**
```json
{
  "invoice_id": "INV-S03",
  "supplier_invoice_number": "SIN-0001",
  "prior_invoice_numbers_on_this_po": [],
  "lines": [
    {
      "line_number": 1,
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "100",
      "uom": "EA",
      "unit_price": "13.70",
      "extended": "1370.00"
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
      "invoiced": "100",
      "invoiced_uom": "EA",
      "ordered": "100",
      "ordered_uom": "EA",
      "received": "100",
      "uom_conversion_factor": null
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
      "po_unit_price": "12.50",
      "invoiced_unit_price": "13.70",
      "delta": "1.20",
      "po_extended": "1250.00",
      "invoiced_extended": "1370.00",
      "extended_amounts_agree": false
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
  "disposition": "request_credit_memo",
  "exception_classes": [
    "price_variance"
  ],
  "rationale": "The invoiced unit price of $13.70 exceeds the PO unit price of $12.50 by $1.20, which is outside the allowable tolerance of $0.50. The extended amounts also do not agree."
}
```

## The proposal

Disposition: **request_credit_memo**
Exception classes claimed: price_variance
Rationale: The invoiced unit price of $13.70 exceeds the PO unit price of $12.50 by $1.20, which is outside the allowable tolerance of $0.50. The extended amounts also do not agree.

## The gate verdict

**Approved.** Verified exception classes: price_variance.

## Gold

Expected disposition: **request_credit_memo**
Why: Unit price 9.6% over PO with goods fully received; supplier owes the difference.