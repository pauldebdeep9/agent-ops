# Case S05
Model: gpt-4o-mini · Outcome: disposition_reached

## The case

| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |
|---|---|---|---|---|---|
| BRG-6204 | 100 EA | 60 EA | 100 EA | $12.50 | $12.50 |

## What the agent did

### Turn 1
Called `get_po`, `get_receipt`, `get_invoice`.

**get_po**
```json
{
  "po_number": "PO-S05",
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
  "receipt_number": "GR-S05",
  "line_count": 1,
  "lines": [
    {
      "po_line_number": 1,
      "part_number": "BRG-6204",
      "quantity_received": "60",
      "uom": "EA"
    }
  ]
}
```

**get_invoice**
```json
{
  "invoice_id": "INV-S05",
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
    }
  ]
}
```

### Turn 2
Called `compare_quantities`.

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
      "received": "60",
      "uom_conversion_factor": null
    }
  ]
}
```

### Turn 3
Called `compare_prices`.

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

### Turn 4
Called `write_proposal`.

**write_proposal**
```json
{
  "recorded": true,
  "disposition": "hold_pending_receipt",
  "exception_classes": [
    "short_receipt"
  ],
  "rationale": "The invoice indicates 100 EA were invoiced, while only 60 EA were received, resulting in a short receipt situation."
}
```

## The proposal

Disposition: **hold_pending_receipt**
Exception classes claimed: short_receipt
Rationale: The invoice indicates 100 EA were invoiced, while only 60 EA were received, resulting in a short receipt situation.

## The gate verdict

**Approved.** Verified exception classes: short_receipt.

## Gold

Expected disposition: **hold_pending_receipt**
Why: Only 60 of 100 received. The invoice may be correct once the balance arrives.