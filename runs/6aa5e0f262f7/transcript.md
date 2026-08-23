# Case S01
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 100 EA | 100 EA | $12.50 | $12.50 |
| SEA-2210 | 40 EA | 40 EA | 40 EA | $3.75 | $3.75 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S01",
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
    },
    {
      "line_number": 2,
      "part_number": "SEA-2210",
      "quantity": "40",
      "uom": "EA",
      "unit_price": "3.75",
      "extended": "150.00"
    }
  ]
}
```

**get_receipt**
```json
{
  "receipt_number": "GR-S01",
  "line_count": 2,
  "lines": [
    {
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity_received": "100",
      "uom": "EA"
    },
    {
      "po_line_number": 2,
      "part_number": "SEA-2210",
      "quantity_received": "40",
      "uom": "EA"
    }
  ]
}
```

**get_invoice**
```json
{
  "invoice_id": "INV-S01",
  "supplier_invoice_number": "SIN-0001",
  "prior_invoice_numbers_on_this_po": [],
  "lines": [
    {
      "line_number": 1,
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity": "100",
      "uom": "EA",
      "unit_price": "12.50",
      "extended": "1250.00"
    },
    {
      "line_number": 2,
      "po_line_number": 2,
      "part_number": "SEA-2210",
      "quantity": "40",
      "uom": "EA",
      "unit_price": "3.75",
      "extended": "150.00"
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
    },
    {
      "invoice_line": 2,
      "po_line": 2,
      "on_po": true,
      "invoiced": "40",
      "invoiced_uom": "EA",
      "ordered": "40",
      "ordered_uom": "EA",
      "received": "40",
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
    },
    {
      "invoice_line": 2,
      "on_po": true,
      "po_unit_price": "3.75",
      "invoiced_unit_price": "3.75",
      "delta": "0.00",
      "po_extended": "150.00",
      "invoiced_extended": "150.00",
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
  "rationale": "All quantities and prices match between the purchase order, goods receipt, and invoice. No exceptions were found."
}
```

## The proposal

Disposition: **auto_match**
Exception classes claimed: none
Rationale: All quantities and prices match between the purchase order, goods receipt, and invoice. No exceptions were found.

## The gate verdict

**Approved.** Verified exception classes: none.

## Gold

Expected disposition: **auto_match**
Why: Both lines agree on quantity, UOM and price across all three documents.