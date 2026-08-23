# Case S08
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 100 EA | 100 EA | $12.50 | $12.50 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S08",
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
  "receipt_number": "GR-S08",
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
  "invoice_id": "INV-S08",
  "supplier_invoice_number": "SIN-8891",
  "prior_invoice_numbers_on_this_po": [
    "SIN-8891"
  ],
  "lines": [
    {
      "line_number": 1,
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "100",
      "uom": "EA",
      "unit_price": "12.50",
      "extended": "1250.00"
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
      "invoiced_unit_price": "12.50",
      "delta": "0.00",
      "po_extended": "1250.00",
      "invoiced_extended": "1250.00",
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
  "disposition": "auto_match",
  "exception_classes": [],
  "rationale": "All quantities and prices match between the purchase order, goods receipt, and invoice."
}
```

## The proposal

Disposition: **auto_match**
Exception classes claimed: none
Rationale: All quantities and prices match between the purchase order, goods receipt, and invoice.

## The gate verdict

**Rejected.** claimed exceptions ['<none>'] do not match verified ['duplicate_invoice']

## Gold

Expected disposition: **reject_duplicate**
Why: Supplier invoice number SIN-8891 is already posted against this PO.