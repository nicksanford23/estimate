# Undownloaded Neon Document Inventory

Source of truth: Neon `estimate.documents` joined to `estimate.permits`.
Downloaded reference: R2 `docs/<doc_id>.pdf` object existence.
Local `data/download_run.csv` and Neon `estimate.document` are included
only as diagnostics.

## Headline

- Raw Neon documents: 34978
- Raw Neon permits represented by documents: 2589
- Download-run rows: 2272
- Downloaded OK doc_ids in download_run: 2251
- Working pipeline downloaded/rendered doc_ids in estimate.document: 104
- R2 docs/<doc_id>.pdf objects matching raw Neon docs: 2260
- Known downloaded/rendered union used for this report: 2260
- Non-OK/failed queued doc_ids in download_run: 21
- Not downloaded OK yet: 32718 documents across 2561 permits
- Never queued in download_run: 32596 documents across 2551 permits

## Permit-Level Download Status

- Permits with at least one document in Neon: 2589
- Permits with at least one known downloaded/rendered doc: 1054
- Fully downloaded permits: 28
- Partially downloaded permits: 1026
- Not-started permits: 1535

| permit_type | fully_downloaded | partially_downloaded | not_started | total_with_docs |
|---|---:|---:|---:|---:|
| NEWC | 6 | 526 | 614 | 1146 |
| RNVN | 0 | 0 | 42 | 42 |
| RNVS | 22 | 500 | 879 | 1401 |

## Undownloaded By Filename Type

| doc_type | docs | permits |
|---|---|---|
| other_pdf | 13093 | 2355 |
| non_pdf_or_message | 9262 | 1524 |
| admin_pdf | 5206 | 1833 |
| struct_civil_site_pdf | 2411 | 859 |
| plan_like_arch_pdf | 1656 | 705 |
| mep_fire_pdf | 1086 | 562 |
| strict_finish_pdf | 2 | 2 |
| interior_set_pdf | 2 | 2 |

## Undownloaded By Permit Type

| permit_type | docs | permits |
|---|---|---|
| NEWC | 17592 | 1140 |
| RNVS | 14321 | 1379 |
| RNVN | 805 | 42 |

## High-Priority Undownloaded Candidates

| doc_type | docs | permits |
|---|---|---|
| other_pdf | 8459 | 1298 |
| plan_like_arch_pdf | 1656 | 705 |
| strict_finish_pdf | 2 | 2 |
| interior_set_pdf | 2 | 2 |

Priority definition:
- 1: strict finish PDF filename
- 2: interior set PDF filename
- 3: broad architectural/plan-like PDF filename
- 4: other PDF with finish/interior/floor/plan terms in permit description

## Top Candidate Permits

| permit | type | candidate_docs | examples |
|---|---|---:|---|
| 14-11290-NEWC | NEWC | 66 | 1381157:IW-2.1 Branch Finish Plan Liberty Bank Gentilly 06.30.14.pdf / 1381111:A-0.0 Cover Sheet Liberty Bank Gentilly 06.30.14.pdf / 1381112:A-0.1 Code Data Plan Liberty Bank Gentilly 06.30.14.pdf / +63 more |
| 20-29653-RNVS | RNVS | 7 | 4941409:Finish schedule.pdf / 4941400:2nd floor reflected ceiling.pdf / 4941402:3rd floor reflected ceiling.pdf / +4 more |
| 20-01153-RNVS | RNVS | 30 | 4623600:200914_CHNO B9_Interior Scope.pdf / 4513552:PLANS.pdf / 4513560:ELEVATION CERT.pdf / +27 more |
| 25-21013-RNVN | RNVN | 6 | 8348102:250710-05 Interior Design.pdf / 8348100:250710-03 Architectural Demolition.pdf / 8348101:250710-04 Architectural.pdf / +3 more |
| 24-16993-NEWC | NEWC | 51 | 7299855:Survey and demo permit set.pdf / 7525646:Wilcox-Academy Daycare_ArchCOMCheck_08-29-24.pdf / 7951491:2723_Freret-floor Framing-Building-02_26_2025-24-16993-newc-C_M commer / +48 more |
| 24-32750-NEWC | NEWC | 41 | 8491996:6325 Cromwell Pl Bldg A - first floor slab - 24-32750-NEWC.pdf / 8491997:6325 Cromwell Pl Bldg A 1st floor slab 9-1-25 NO 24-32750NEWC JH.pdf / 8517366:6325 Cromwell Pl Bldg A - first floor slab - 24-32750-NEWC (1).pdf / +38 more |
| 16-18599-NEWC | NEWC | 38 | 2506479:Tenant build out plumbing drawings for reference only.pdf / 2372635:AR-16-008993-062020160436.pdf / 2372636:AR-16-008993-CautionaryCodes-062020160436.pdf / +35 more |
| 22-23361-NEWC | NEWC | 37 | 5845650:2110 NOLA AC 221111 Foundation Permit Set.pdf / 5849291:2110 NOLA AC 221111 Foundation Permit Set Arch Stamped.pdf / 5860932:22160_STORMWATER MANAGEMENT PLAN REPORT_10-31-22.pdf / +34 more |
| 21-21797-RNVS | RNVS | 36 | 5840195:2121 Chartres St Final Drawings__Civil.pdf / 5840196:2121 Chartres St Final Drawings__Electrical.pdf / 5840197:2121 Chartres St Final Drawings__Mechanical.pdf / +33 more |
| 14-14229-NEWC | NEWC | 35 | 1491958:DEPARTMENT OF SAFETY AND PERMITS Plan Review Comments.pdf / 2182665:revised elevation certificate.pdf / 1302053:2013-164 - Cobalt Rehabilitation Hospital New Orleans.pdf / +32 more |
| 17-32126-RNVS | RNVS | 35 | 3029706:2301 St.Claude Avenue-A1.0.pdf / 3029707:2301 St.Claude Avenue-A2.0.pdf / 3309361:A2.1.pdf / +32 more |
| 24-14124-RNVN | RNVN | 35 | 7249329:Architecture set_Tulane (RCC).pdf / 7253399:N23-021 Trader Joes NO MEP Permit Set.pdf / 7253401:2136A102-Layout1.pdf / +32 more |
| 16-16205-NEWC | NEWC | 34 | 2574369:HouseofPrayer 11-6-16-Planting 24x36 (2).pdf / 2800071:approved plans for ocnstruction.pdf / 3788712:HAHofP Rev 10-26-18-1.1 Ex Site Plan.pdf / +31 more |
| 13-12959-NEWC | NEWC | 33 | 830621:SP1 Site Plan.pdf / 830625:A2 FIRE RATED ASSEMBLIES.pdf / 830626:A2A ACCESSIBILITY STANDARDS.pdf / +30 more |
| 13-48782-NEWC | NEWC | 33 | 1067350:elevation benchmark certificate.pdf / 1098270:A4.0_R1_Bidding.pdf / 1101038:A4.0_R1_Bidding.pdf / +30 more |
| 14-03595-NEWC | NEWC | 33 | 1139274:Permit no 14-03595-NEWC - Site Plan with DPW stamp.pdf / 1099629:JMC - CURRENT Artists' Studio Building_Project Manual.pdf / 1099705:1464 N.Rocheblave St.pdf / +30 more |
| 24-30328-NEWC | NEWC | 33 | 7890066:P-100 Water Gas Plan_D8571.pdf / 7890068:P-101 Waste Vent Plan_D8571.pdf / 8897923:S-100_Foundation Plan-D8571, rev (RCC).pdf / +30 more |
| 24-29387-NEWC | NEWC | 32 | 7596555:1141 Esplanade HDLC 100324.pdf / 7806345:2401301-Esplanade-Dellile Apartments_Elec.pdf / 7806346:2401301-Esplanade-Dellile Apartments_Plbg.pdf / +29 more |
| 16-16972-NEWC | NEWC | 31 | 2323187:41-15 Elect. TCI Mega Plastic Permit Set.pdf / 2326225:41-15 Elect. TCI Mega Plastic Permit Set.pdf / 2697075:11567 -TCI - L201 - DRAINAGE PLAN - REVISED 1-24-17.pdf / +28 more |
| 26-00820-NEWC | NEWC | 31 | 9027612:100-02 SITE PLAN - 15140-42 INTRACOASTAL.pdf / 8943389:Yard Building Erection Job Costs.pdf / 8944162:E3.pdf / +28 more |
| 20-21014-RNVS | RNVS | 29 | 4647669:20-118 801 PATTERSON ELECTRICAL SET- E0.2-BUILDING ELECTRICAL PLAN S a / 4720115:801 Patterson - R.O.W. Trees Plan.pdf / 4721784:PKWY Approved ROW Tree Plan 1DEC2020.pdf / +26 more |
| 14-17089-NEWC | NEWC | 28 | 1416059:14-17089_Public Works Approved site plan.pdf / 1471782:14-17089-NEWC_DPW Approved Site Plan.pdf / 1340760:14_0523_The Beacon_Permit Project Manual.pdf / +25 more |
| 24-16471-RNVS | RNVS | 28 | 7557938:333 N Diamond ROW Landscape Plan-PKWY APP.pdf / 7558219:333 N Diamond ROW Landscape Plan-PKWY APP (1).pdf / 7695616:240917_NOFD Plan Review 333 N Diamond St.pdf / +25 more |
| 24-17262-NEWC | NEWC | 28 | 7531584:PLUMBING 2024-08-29 Millennium Place RISER PAGE 23 - Plan Check - P.pd / 7531616:MECHANICAL 2024-08-29 Millennium Place - Plan Check - M.pdf / 7561324:DPW Approved Site Plan.pdf / +25 more |
| 24-24910-RNVS | RNVS | 28 | 7816101:3239_P301_PLUMB DETAILS Layout1 (1)_NH_MR.pdf / 7858965:3239_P301_PLUMB DETAILS Layout1 (1)_NH_MR (1).pdf / 7929278:Riverside Lofts - Plan Review Response.pdf / +25 more |
| 25-09195-RNVN | RNVN | 28 | 8021831:250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECT / 8021832:250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECT / 8021833:250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECT / +25 more |
| 14-18929-NEWC | NEWC | 27 | 1584592:ISH-Site Plan-20141124.pdf / 1605758:Site Plan-DPW approved.pdf / 1353449:ISH_ARC Sight Line Studies.pdf / +24 more |
| 16-20227-NEWC | NEWC | 27 | 2374587:1818 Carondelet elevation certificate.pdf / 2398984:1818 Carondelet St revised plot plan.pdf / 2356827:1818 Carondelet St benchmark calculations.pdf / +24 more |
| 17-26365-NEWC | NEWC | 27 | 3955449:1824 CARONDELET ST. - FINAL FEMA FLOOD ELEVATION and SURVEY.pdf / 2952783:1822 Carondelet_Documents.pdf / 2952791:1822 Carondelet St pile load.pdf / +24 more |
| 22-28198-NEWC | NEWC | 27 | 5746269:220701 Mazant Royal - Civil Permit Set.pdf / 5746270:220701 Mazant Royal - Electrical Permit Set.pdf / 5746271:220701 Mazant Royal - Fire Protection Permit Set.pdf / +24 more |
| 23-02738-RNVS | RNVS | 27 | 5969688:Approved 2002 JOSEPHINE ST Plan.pdf / 6172740:2000-02 JOSEPHINE STREET-A1.pdf / 6172741:2000-02 JOSEPHINE STREET-A2.pdf / +24 more |
| 13-14264-NEWC | NEWC | 26 | 982082:13-14264 APPROVED PLAN SET VOL 2.pdf / 982083:13-14264 APPROVED PLAN SET VOL 1.pdf / 826083:11028 BID PM Vol 1_compiled w_AIA Docs 130422.pdf / +23 more |
| 16-34101-NEWC | NEWC | 25 | 3694627:15031_FABC_Paving Plan.pdf / 2512468:FABC - Specifications - 8.4.16.pdf / 2521114:2- FABC Landscape.pdf / +22 more |
| 25-09220-NEWC | NEWC | 25 | 8493141:2401301-Esplanade-Dellile Apartments_Elec.pdf / 8493142:2401301-Esplanade-Dellile Apartments_Mech.pdf / 8544650:2025.09.16 - Esplanade-Dellile Apartments - Permit Comments LCG Respon / +22 more |
| 25-17248-RNVS | RNVS | 25 | 8660868:615 Baronne - Plan Review Response - 2025.11.03.pdf / 8232884:615 Baronne Street - ARC Package 1 - 2025.06.06.pdf / 8645860:615 Baronne Street - Compiled 100 CDs - 2025.10.25Part-1.pdf / +22 more |
| 18-12867-NEWC | NEWC | 24 | 6123371:3321 St. Charles framing (partial on 1st floor) 18-12867-newc cm 05-04 / 6123373:3321_St._Charles-Framing partial 1st floor-05_04_2023-18-12867-newc-C_ / 3364880:McD St. Charles Ave.- HDLC submit 4-17-18.pdf / +21 more |
| 19-00670-RNVS | RNVS | 24 | 4924051:SWMP Plan set 04-21-21 SENT.pdf / 5005793:A1.0 Title 6_9_21.pdf / 5011413:A5.0 Cross Section 6_11_21.pdf / +21 more |
| 22-18919-NEWC | NEWC | 24 | 5589748:2256 Baronne_Storm Water Management Plan.pdf / 5592078:2256 Baronne_Storm Water Management Plan (1).pdf / 5592080:2256 Baronne_Civil Drawings.pdf / +21 more |
| 13-27145-NEWC | NEWC | 23 | 926984:ITEM 3 - MULTI-PURPOSE PLAN.pdf / 864170:8012 Oak St.pdf / 864185:- 0 StAndrew ProjManual.pdf / +20 more |
| 14-06082-NEWC | NEWC | 23 | 1187746:Attachment 5 Revised M-1 Floor Plan - HVAC-Layout.pdf / 1809668:Approved stamped plans for construction.pdf / 1126113:Final Report.pdf / +20 more |
