# Case S04
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 100 EA | 120 EA | $12.50 | $12.50 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S04",
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
  "receipt_number": "GR-S04",
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
  "invoice_id": "INV-S04",
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
      "invoiced_unit_price": "12.50",
      "delta": "0.00",
      "po_extended": "1250.00",
      "invoiced_extended": "1500.00",
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
    "quantity_over_invoiced"
  ],
  "rationale": "The invoice includes 120 units of part number BRG-6204, while the purchase order and goods receipt confirm only 100 units were ordered and received. A credit memo is requested for the over-invoiced quantity."
}
```

## The proposal

Disposition: **request_credit_memo**
Exception classes claimed: quantity_over_invoiced
Rationale: The invoice includes 120 units of part number BRG-6204, while the purchase order and goods receipt confirm only 100 units were ordered and received. A credit memo is requested for the over-invoiced quantity.

## The gate verdict

**Approved.** Verified exception classes: quantity_over_invoiced.

## Gold

Expected disposition: **request_credit_memo**
Why: Invoiced 120 EA against 100 EA received; 20 EA were never delivered.