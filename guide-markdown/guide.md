---
document_id: "/Content/Guide/guide.ditamap"
version: "3"
snapshot: "/Snapshots/guide_v3"
snapshot_status: "Published"
snapshot_created: "2026-10-10T09:00:00Z"
flavor: "markdown_github"
layout: "single"
converted_at: "2026-11-06T01:20:06+00:00"
source: "IXIA CCMS"
---

# GTS Sample User Guide

## Contents

- [GTS Transceiver Overview](#gts-transceiver-overview)
    - [GTS Transceiver Design Flow](#gts-transceiver-design-flow)
- [GTS Transceiver Architecture](#gts-transceiver-architecture)
    - [PMA Details](#pma-details)
- [Appendices](#appendices)
    - [Glossary](#glossary)

<a id="gts-transceiver-overview"></a>

## GTS Transceiver Overview

This guide describes the GTS transceivers in Agilex™ 3 FPGAs.

The transceiver supports data rates of 1–12.5 Gbps with **NRZ** signaling.

**Key GTS Transceiver Features**

|Feature|Support|
|-------|-------|
|Number of available PMAs|4 PMAs|
|Data rate range|1–12.5 Gbps NRZ|

**Note:** Devices with GTS transceiver and HPS only.

-   Architecture details
-   IP implementation

**Related information**

[GTS Transceiver Architecture](#gts-transceiver-architecture)

<a id="gts-transceiver-design-flow"></a>

### GTS Transceiver Design Flow

Integrate a GTS transceiver PHY system with three IPs, as shown in the flow chart.

1.  Instantiate the `GTS PMA/FEC Direct PHY IP`.

2.  Connect the clocks.

    **Important:** Use the System PLL Clocks IP.

![Design flow chart](images/flow.png "GTS Transceiver Design Flow")

*GTS Transceiver Design Flow*

<a id="gts-transceiver-architecture"></a>

## GTS Transceiver Architecture

### Building Blocks

The bank holds four PMAs.

### PMA Architecture

See [the overview](#gts-transceiver-overview).

<a id="pma-details"></a>

### PMA Details

Each PMA has a transmitter and a receiver. The flow is shown below and in [the design flow](#gts-transceiver-design-flow).

![PMA block diagram](images/flow.png "PMA Block Diagram")

*PMA Block Diagram*

#### Transmitter

Serializes data.

<a id="appendices"></a>

## Appendices

<a id="glossary"></a>

### Glossary

**PMA:** Physical Medium Attachment. See [the overview](#gts-transceiver-overview).
