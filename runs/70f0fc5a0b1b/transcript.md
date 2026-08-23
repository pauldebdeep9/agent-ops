# Case S07
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 100 EA | 100 EA | $12.50 | $12.50 |
| FRT-EXP | — (not on PO) | — | 1 EA | — | $220.00 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S07",
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
  "receipt_number": "GR-S07",
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
  "invoice_id": "INV-S07",
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
      "po_line_number": null,
      "part_number": "FRT-EXP",
      "quantity": "1",
      "uom": "EA",
      "unit_price": "220.00",
      "extended": "220.00"
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
      "po_line": null,
      "on_po": false,
      "invoiced": "1",
      "invoiced_uom": "EA",
      "ordered": null,
      "ordered_uom": null,
      "received": "0",
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
      "on_po": false,
      "invoiced_unit_price": "220.00"
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
  "disposition": "request_po_amendment",
  "exception_classes": [
    "part_not_on_po"
  ],
  "rationale": "The invoice includes a charge for part FRT-EXP, which is not listed on the purchase order. A PO amendment is required to address this additional charge."
}
```

## The proposal

Disposition: **request_po_amendment**
Exception classes claimed: part_not_on_po
Rationale: The invoice includes a charge for part FRT-EXP, which is not listed on the purchase order. A PO amendment is required to address this additional charge.

## The gate verdict

**Approved.** Verified exception classes: part_not_on_po.

## Gold

Expected disposition: **request_po_amendment**
Why: Freight line is legitimate but unreferenced; the PO needs a line for it.