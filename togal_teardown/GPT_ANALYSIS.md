**You gave enough screenshots. I do not need another batch.**

**First, I should tighten one thing from my earlier feedback.**

**\#\# What “semantic classification” means here**

**Togal performs two distinct jobs:**

**1\. \*\*Geometry detection:\*\* find enclosed polygons and calculate area/perimeter.**

**2\. \*\*Semantic classification:\*\* decide what each polygon represents—bedroom, bathroom, corridor, shaft, balcony, closet, and so on.**

**At \*\*02:39\*\*, Togal has already found the geometry and then assigns room-type labels. The right panel shows categories such as:**

**\* Corridor — 1**

**\* Bedroom — 20**

**\* Bathroom — 23**

**\* Closet — 22**

**\* Shafts — 85**

**\* Balcony — 1**

**The important error is \*\*not that all 85 shaft polygons are necessarily wrong\*\*. My earlier wording risked implying that, and the later screenshots show that would be too strong.**

**What the video proves is that \*\*the “Shafts” classification contains a mixture of true shafts and balcony-like areas\*\*. At \*\*03:50–04:06\*\*, the presenter says some balconies were labeled as shafts and then notices that true shafts in the building core are also part of the same selection. He subsequently cleans that selection up, apparently deleting the actual shaft polygons from the flooring classification at approximately \*\*04:15–04:21\*\*.**

**So the more precise finding is:**

**\> Togal’s automatic room-type classification grouped some materially different spaces into the same class. The human could correct it quickly, but the interface did not identify which members of the class were uncertain or incorrect.**

**\#\#\# “Same saturated color and numerical authority”**

**At \*\*02:39\*\*, “Bathroom — 23 — 1,361 SF” and “Shafts — 85 — 1,357 SF” are presented in the same manner:**

**\* A solid category color**

**\* An exact polygon count**

**\* An exact square-foot total**

**\* No confidence level**

**\* No warning icon**

**\* No “review recommended” state**

**Yet the presenter later confirms that at least some members of the shaft class are actually balconies.**

**That does \*\*not\*\* mean the measurements themselves are necessarily wrong. It means the system visually presents an imperfect classification with the same certainty as a seemingly correct one. The risk is that a user can batch-assign a material to an entire category before noticing it contains mixed spaces—which is essentially what the presenter does before cleaning it up.**

**The positive side is equally important: the demo shows that the mistake is recoverable through visual review and batch editing.**

**\---**

**\# Competitive teardown: Togal.AI flooring takeoff**

**\#\# Executive assessment**

**Togal’s strongest demonstrated advantage is not flawless AI. It is a mature, fast interaction model around imperfect AI:**

**\> Generate a large amount of geometry automatically, organize it into selectable classes, and give the estimator conventional editing tools to finish the job.**

**The video does \*\*not\*\* demonstrate a fully automatic flooring takeoff derived from finish schedules. It demonstrates:**

**\* Automatic room geometry**

**\* Automatic room-type classification**

**\* Manual mapping of those room types to flooring materials**

**\* Manual cleanup of classification mistakes**

**\* Immediate quantity rollups**

**That distinction matters. Togal meaningfully reduces drawing labor, but the estimator remains responsible for understanding the finish scope, assigning materials, finding misclassifications, and excluding non-flooring areas.**

**Your proposed approach is more flooring-specific and potentially more defensible, but it is currently an architectural claim rather than demonstrated product performance. Togal is ahead in production maturity, editing ergonomics, breadth, and likely commercial distribution. Your possible opening is not “our AI draws polygons better.” It is:**

**\> Our system tells the estimator exactly which flooring quantities are supported, which still need review, and where every material assignment came from.**

**\---**

**\# 1\. Feature inventory**

**\#\# Project and document intelligence**

**| Capability                                                                   | Evidence                                                                                                                        |           Timestamp |**

**| \---------------------------------------------------------------------------- | \------------------------------------------------------------------------------------------------------------------------------- | \------------------: |**

**| Project workspace containing multiple drawing disciplines and specifications | \*\*\[demonstrated on screen\]\*\* — folders for architectural, electrical, mechanical, roof plans, specs, and other sets are visible |               00:12 |**

**| Large project-set organization                                               | \*\*\[demonstrated on screen\]\*\* — the project library visibly contains hundreds of documents/pages                                 |               00:12 |**

**| Upload drawings into the project                                             | \*\*\[implied/ambiguous\]\*\* — “Upload Drawings” button is visible, but upload is not performed                                      |               00:12 |**

**| Share a project                                                              | \*\*\[implied/ambiguous\]\*\* — Share button is visible but unused                                                                    |               00:12 |**

**| Chat against the project documents                                           | \*\*\[demonstrated on screen\]\*\*                                                                                                    |         00:26–00:30 |**

**| Switch chat scope to the entire project                                      | \*\*\[demonstrated on screen\]\*\* — “Ask the project” mode is shown                                                                  |               00:30 |**

**| Generate a flooring scope summary                                            | \*\*\[demonstrated on screen\]\*\* — prompt and structured flooring list are visible                                                  |         00:35–00:50 |**

**| Generate a detailed flooring-finish overview                                 | \*\*\[demonstrated on screen\]\*\*                                                                                                    |         00:53–01:04 |**

**| Retrieve information from sheets and specifications                          | \*\*\[claimed verbally only\]\*\* — presenter says the model pulls from uploaded sheets/specs rather than Google                      |         01:10–01:20 |**

**| Provide document/page links in chat answers                                  | \*\*\[demonstrated on screen\]\*\* — at least one answer contains clickable-looking sheet/page references                             | approximately 00:30 |**

**| Admit when requested information cannot be found                             | \*\*\[demonstrated on screen\]\*\* — supplier query receives a qualified “could not find” response                                    | approximately 00:30 |**

**| Citation for every chat assertion                                            | \*\*\[implied/ambiguous\]\*\* — some references are visible, but the full finish list does not visibly cite every item                |         00:30–01:20 |**

**| Live chat response speed                                                     | \*\*\[not demonstrated\]\*\* — completed answers are shown, but generation latency is not                                             |                     |**

**\#\# Automatic drawing analysis**

**| Capability                                                                                       | Evidence                                                                                                    |                 Timestamp |**

**| \------------------------------------------------------------------------------------------------ | \----------------------------------------------------------------------------------------------------------- | \------------------------: |**

**| Open and interact with a floor-plan sheet                                                        | \*\*\[demonstrated on screen\]\*\*                                                                                |                     01:29 |**

**| Run an AI takeoff on the active sheet                                                            | \*\*\[demonstrated on screen\]\*\*                                                                                |               01:35–01:53 |**

**| Configure which takeoff types to generate                                                        | \*\*\[demonstrated on screen\]\*\*                                                                                |       approximately 01:35 |**

**| Generate net area                                                                                | \*\*\[demonstrated on screen\]\*\*                                                                                |               01:53–02:24 |**

**| Generate gross area                                                                              | \*\*\[demonstrated on screen\]\*\* as an available/result layer                                                   | approximately 01:35–01:58 |**

**| Generate building footprint                                                                      | \*\*\[demonstrated on screen\]\*\* as an available/result layer                                                   | approximately 01:35–01:58 |**

**| Generate gross internal area                                                                     | \*\*\[demonstrated on screen\]\*\* as an available/result layer                                                   | approximately 01:35–01:58 |**

**| Generate door area                                                                               | \*\*\[demonstrated on screen\]\*\* as an available/result layer                                                   | approximately 01:35–01:58 |**

**| Generate wall centerline quantities                                                              | \*\*\[demonstrated on screen\]\*\*                                                                                | approximately 01:35–01:58 |**

**| Generate door centerlines                                                                        | \*\*\[demonstrated on screen\]\*\* as an available layer                                                          | approximately 01:35–01:58 |**

**| Generate wall perimeter                                                                          | \*\*\[demonstrated on screen\]\*\*                                                                                | approximately 01:35–01:58 |**

**| Detect and count drawing objects such as toilets, sinks, bathtubs, doors, tables, and appliances | \*\*\[demonstrated on screen\]\*\* — count categories and EA totals appear in the sidebar                         |               01:53–01:58 |**

**| Remove wall thickness from net flooring polygons                                                 | \*\*\[demonstrated on screen\]\*\* visually and \*\*\[claimed verbally only\]\*\* in explanation                        |               02:05–02:24 |**

**| Automatically isolate individual rooms and spaces                                                | \*\*\[demonstrated on screen\]\*\*                                                                                |               02:05–02:24 |**

**| Work on “any floor plan” in the same way                                                         | \*\*\[claimed verbally only\]\*\* and not supported by the single example                                         |               02:05–02:09 |**

**| Display a processing state                                                                       | \*\*\[demonstrated on screen\]\*\*                                                                                | approximately 01:48–01:50 |**

**| Complete the page takeoff in roughly 10 seconds                                                  | \*\*\[demonstrated on screen in the edited recording\]\*\*, not an independently verified benchmark               | approximately 01:46–01:57 |**

**| Read or establish drawing scale automatically                                                    | \*\*\[implied/ambiguous\]\*\* — scale is visible as 1/8" \= 1'-0", but setup and validation are omitted            |              01:29 onward |**

**| Rerun the AI takeoff                                                                             | \*\*\[demonstrated on screen\]\*\* through the Re-Togal/run workflow, although preservation of edits is not shown |       approximately 01:35 |**

**\#\# Review and geometry interaction**

**| Capability                                            | Evidence                                                                                                            |                 Timestamp |**

**| \----------------------------------------------------- | \------------------------------------------------------------------------------------------------------------------- | \------------------------: |**

**| Hide/show takeoff layers                              | \*\*\[demonstrated on screen\]\*\*                                                                                        |               01:53–02:05 |**

**| Isolate only net-area polygons                        | \*\*\[demonstrated on screen\]\*\*                                                                                        |                     02:05 |**

**| Display polygon area and perimeter on selection/hover | \*\*\[demonstrated on screen\]\*\* — examples such as 300 SF / 92 FT                                                      | approximately 02:18–02:24 |**

**| Select all polygons with Ctrl+A                       | \*\*\[demonstrated on screen\]\*\*                                                                                        |               02:29–02:30 |**

**| Box-select multiple polygons                          | \*\*\[claimed verbally only\]\*\* in this sequence; selection behavior is plausible but not separately shown clearly      |               02:29–02:32 |**

**| Show aggregate SF and perimeter for a multi-selection | \*\*\[demonstrated on screen\]\*\* — approximately 15,525 SF and 6,730 FT                                                 |                     02:30 |**

**| Right-click contextual editing                        | \*\*\[demonstrated on screen\]\*\*                                                                                        |              02:35 onward |**

**| Copy selected features                                | \*\*\[implied/ambiguous\]\*\* — menu item visible but unused                                                              |                     02:35 |**

**| Duplicate selected features                           | \*\*\[implied/ambiguous\]\*\* — menu item visible but unused                                                              |                     02:35 |**

**| Delete selected features                              | \*\*\[demonstrated on screen\]\*\* with a confirmation dialog                                                             | approximately 04:15–04:21 |**

**| Group, combine, flip, and rotate selections           | \*\*\[implied/ambiguous\]\*\* — toolbar controls visible, but their flooring usefulness and behavior are not demonstrated |              02:30 onward |**

**| 2D/3D viewing                                         | \*\*\[implied/ambiguous\]\*\* — toggles visible, 3D is not opened                                                         |                throughout |**

**\#\# Room-type classification**

**| Capability                                                                                                                     | Evidence                                                                                            |   Timestamp |**

**| \------------------------------------------------------------------------------------------------------------------------------ | \--------------------------------------------------------------------------------------------------- | \----------: |**

**| Automatically classify room polygons into semantic room types                                                                  | \*\*\[demonstrated on screen\]\*\*                                                                        | 02:35–02:40 |**

**| Room types include corridor, hotel room, living area, bedroom, bathroom, closet, elevator, utility, shaft, balcony, and others | \*\*\[demonstrated on screen\]\*\*                                                                        | 02:39–02:48 |**

**| AutoClassify uses drawing cues to infer room type                                                                              | \*\*\[claimed verbally only\]\*\* — the specific features or evidence used are not disclosed              | 02:40–02:48 |**

**| Color-code polygons by classification                                                                                          | \*\*\[demonstrated on screen\]\*\*                                                                        |       02:39 |**

**| Show count and SF total per room class                                                                                         | \*\*\[demonstrated on screen\]\*\*                                                                        |       02:39 |**

**| Automatically classify every room correctly                                                                                    | \*\*\[not claimed consistently and disproven by the demo\]\*\* — presenter explicitly acknowledges errors | 03:50–04:15 |**

**| Quickly correct an incorrect classification                                                                                    | \*\*\[demonstrated on screen\]\*\* through batch selection, reassignment, and deletion/cleanup            | 03:50–04:21 |**

**| Show model confidence per room                                                                                                 | \*\*\[not shown\]\*\*                                                                                     |             |**

**| Separate confirmed, uncertain, and failed classifications                                                                      | \*\*\[not shown\]\*\*                                                                                     |             |**

**| Show why a room received a particular label                                                                                    | \*\*\[not shown\]\*\*                                                                                     |             |**

**\#\# Material assignment**

**| Capability                                                                 | Evidence                                                                                                  |                  Timestamp |**

**| \-------------------------------------------------------------------------- | \--------------------------------------------------------------------------------------------------------- | \-------------------------: |**

**| Maintain user-defined measurement/material classifications                 | \*\*\[demonstrated on screen\]\*\* in the quantity tree and \*\*\[claimed verbally only\]\*\* as a user-built library |               02:55 onward |**

**| Organize flooring under groups such as Carpet, Tile, and Polished Concrete | \*\*\[demonstrated on screen\]\*\*                                                                              |  approximately 03:04–04:45 |**

**| Add or bring material classifications into the takeoff                     | \*\*\[demonstrated on screen\]\*\* at least as an end state; the full library-setup process is not shown        |                02:55–03:10 |**

**| Select multiple similar rooms and assign one material                      | \*\*\[demonstrated on screen\]\*\*                                                                              |                03:13–03:29 |**

**| Assign LVT Type 1, LVT Type 2, and LVT Type 3                              | \*\*\[demonstrated on screen\]\*\*                                                                              |                03:20–03:46 |**

**| Assign corridor to carpet                                                  | \*\*\[demonstrated on screen\]\*\*                                                                              |  approximately 03:37–03:40 |**

**| Assign balcony areas to polished concrete                                  | \*\*\[demonstrated on screen\]\*\*                                                                              |  approximately 03:50–04:02 |**

**| Use nested right-click menus for material assignment                       | \*\*\[demonstrated on screen\]\*\*                                                                              |                03:20–03:46 |**

**| Show recently used classifications                                         | \*\*\[demonstrated on screen\]\*\* as a menu option                                                             | approximately 03:20 onward |**

**| “Create and assign” a new classification                                   | \*\*\[implied/ambiguous\]\*\* — option visible, not executed                                                    |               02:35 onward |**

**| Automatically derive room materials from the finish schedule               | \*\*\[not shown\]\*\*                                                                                           |                            |**

**| Automatically join room number/name to a schedule row                      | \*\*\[not shown\]\*\*                                                                                           |                            |**

**| Carry source evidence from material assignment                             | \*\*\[not shown\]\*\*                                                                                           |                            |**

**\#\# Quantities and output**

**| Capability                                                                    | Evidence                                                                                                                |          Timestamp |**

**| \----------------------------------------------------------------------------- | \----------------------------------------------------------------------------------------------------------------------- | \-----------------: |**

**| Show final SF by material                                                     | \*\*\[demonstrated on screen\]\*\*                                                                                            |        04:31–04:45 |**

**| Show counts of material polygons/areas                                        | \*\*\[demonstrated on screen\]\*\*                                                                                            |        04:31–04:45 |**

**| Convert tile/LVT area into derived piece or package quantities                | \*\*\[demonstrated on screen\]\*\*, although the exact column definitions are hard to read                                    |        04:31–04:45 |**

**| Store tile dimensions in classification names, such as 14×14, 6×12, and 10×10 | \*\*\[demonstrated on screen\]\*\*                                                                                            |        04:31–04:45 |**

**| Include price per square foot                                                 | \*\*\[claimed verbally only\]\*\*; apparent pricing columns exist, but no clear configured dollar calculation is demonstrated |        04:36–04:42 |**

**| Quantities tab                                                                | \*\*\[demonstrated on screen\]\*\* as the active view                                                                         | throughout takeoff |**

**| Breakdown view                                                                | \*\*\[implied/ambiguous\]\*\* — tab visible but unused                                                                        |         throughout |**

**| Export                                                                        | \*\*\[implied/ambiguous\]\*\* — tab visible but unused                                                                        |         throughout |**

**| Export PDF                                                                    | \*\*\[implied/ambiguous\]\*\* — control visible but unused                                                                    |         throughout |**

**| Compare drawings/takeoffs                                                     | \*\*\[implied/ambiguous\]\*\* — control visible but unused                                                                    |         throughout |**

**| Rate the AI takeoff as Great, OK, or Poor                                     | \*\*\[demonstrated on screen\]\*\*                                                                                            |       01:53 onward |**

**| Convert that rating into structured geometry/model training data              | \*\*\[not shown\]\*\*                                                                                                         |                    |**

**\---**

**\# 2\. Workflow reconstruction**

**\#\# A. Project understanding**

**\#\#\# 1\. Enter the project**

**The user opens a project containing drawing sets and specifications at \*\*00:12\*\*. The project is already organized. Upload time, document processing time, page classification, and any manual folder setup are skipped.**

**\#\#\# 2\. Open Togal Chat**

**At \*\*00:26\*\*, the user opens the chat panel and switches to asking the entire project at \*\*00:30\*\*.**

**\#\#\# 3\. Request a flooring scope summary**

**The user asks for a flooring scope, separated by areas or finish designation, at \*\*00:35–00:41\*\*. A structured list of materials appears at \*\*00:44–00:50\*\*.**

**A second prompt requests a more detailed overview at \*\*00:53–00:56\*\*.**

**\*\*Automatic:\*\* searching project documents and composing the answer.**

**\*\*Human involvement:\*\* writing a useful prompt and deciding whether the answer is complete or correct.**

**\*\*Not shown:\*\***

**\* Generation latency**

**\* Whether every answer statement has a citation**

**\* Whether the listed finish designations were cross-checked against the room finish schedule**

**\* How conflicts between specifications and drawings are handled**

**\* Addenda or revision priority**

**\#\# B. Generate the geometry**

**\#\#\# 4\. Open one floor plan**

**At \*\*01:29\*\*, the presenter opens a clean, repetitive multifamily/hotel floor plan.**

**\#\#\# 5\. Choose automatic takeoff outputs**

**At approximately \*\*01:35\*\*, the user opens a takeoff settings panel and checks multiple extraction types, including net area, gross area, footprint, walls, doors, and counts.**

**\#\#\# 6\. Run the takeoff**

**The user presses Go. Processing is visible around \*\*01:48–01:50\*\*, and the completed overlays appear around \*\*01:53–01:57\*\*.**

**The edited recording depicts approximately \*\*10–12 seconds\*\* of processing. This should not be treated as a reliable production benchmark because:**

**\* The recording may contain cuts**

**\* Server load is unknown**

**\* The PDF was already uploaded and processed**

**\* Only one favorable page is tested**

**\#\#\# 7\. Isolate the relevant flooring layer**

**The user hides other extraction layers and focuses on net area at \*\*02:05–02:24\*\*.**

**The user can inspect area and perimeter for individual polygons. The polygons appear to follow interior wall faces rather than wall centerlines.**

**\#\# C. Automatically label room types**

**\#\#\# 8\. Select all generated net-area shapes**

**At \*\*02:29–02:30\*\*, the presenter uses Ctrl+A or a selection box. The aggregate selection shows approximately \*\*15,525 SF\*\* and \*\*6,730 FT\*\*.**

**\#\#\# 9\. Run AutoClassify**

**At \*\*02:35\*\*, the user right-clicks and chooses Auto Classify.**

**By approximately \*\*02:39\*\*, the polygons have changed from one green takeoff layer into multiple colors representing inferred room types.**

**The video depicts roughly four seconds for this operation, again without proving that time under normal conditions.**

**\#\#\# 10\. Review classifications**

**The resulting room taxonomy includes bathrooms, bedrooms, corridors, closets, shafts, balconies, and other types.**

**The presenter does not systematically verify each category. He proceeds directly to material assignment, relying on visual familiarity with the plan.**

**\#\# D. Build the flooring takeoff**

**\#\#\# 11\. Bring in flooring classifications**

**At approximately \*\*02:55–03:10\*\*, the presenter uses a prebuilt classification library containing carpet, tile/LVT types, and polished concrete.**

**The actual initial setup of this library is not shown. The phrase “library that I have built out” implies prior configuration.**

**\#\#\# 12\. Assign materials in batches**

**The user selects groups of similar polygons and assigns flooring:**

**\* Hotel/living areas → LVT Type 1 at approximately \*\*03:13–03:20\*\***

**\* Bedrooms → LVT Type 2 at approximately \*\*03:24–03:29\*\***

**\* Corridor → Carpet Type 1 around \*\*03:33–03:40\*\***

**\* Bathrooms → LVT Type 3 around \*\*03:40–03:46\*\***

**\* Balcony-like regions → Polished Concrete around \*\*03:50–04:02\*\***

**The interaction pattern is:**

**\> Select matching polygons → right-click → navigate the classification tree → assign material.**

**This is materially faster than tracing each space manually, but the finish determination itself is human-driven.**

**\#\# E. Correct an AI mistake**

**\#\#\# 13\. Discover a mixed room classification**

**The presenter notices that some balcony polygons were classified as shafts, while actual shafts also exist in the core at \*\*03:50–04:08\*\*.**

**\#\#\# 14\. Clean up the selection**

**He selects the inappropriate features and removes or reclassifies them. The screenshots show a delete confirmation around \*\*04:15–04:21\*\*.**

**This correction is manual, visual, and fast. The software does not appear to:**

**\* Explain why the classification failed**

**\* Flag the class in advance**

**\* Record a structured “balcony misclassified as shaft” correction visibly**

**\* Show that the correction will improve future predictions**

**\#\# F. Inspect final quantities**

**\#\#\# 15\. Expand the quantity tree**

**At \*\*04:31–04:45\*\*, the final takeoff shows approximately:**

**\* Carpet Type 1 — \*\*1,511 SF\*\***

**\* LVT Type 3 — \*\*1,361 SF\*\***

**\* LVT Type 2 — \*\*2,783 SF\*\***

**\* LVT Type 1 — \*\*6,267 SF\*\***

**\* Polished Concrete — \*\*786 SF\*\***

**The material-assigned total is roughly \*\*12,708 SF\*\*, compared with approximately \*\*15,524 SF\*\* of generated net area.**

**That gap may be legitimate—shafts, elevators, stairs, utilities, and excluded spaces—but the UI does not visibly present a reconciliation such as:**

**\* Assigned flooring**

**\* Intentionally excluded**

**\* Still unassigned**

**\* Failed/unmeasured**

**The estimator must infer completeness from the category tree.**

**\#\# Conspicuously not shown**

**\* Upload and preprocessing duration**

**\* Scale detection or calibration**

**\* Scale mismatch handling**

**\* Multi-page batch takeoff**

**\* Multiple floors or buildings**

**\* Repeated-sheet deduplication**

**\* Finish-schedule extraction joined to room polygons**

**\* Room numbers matched to schedule rows**

**\* Open-plan spaces without closed walls**

**\* Curved walls**

**\* Irregular renovations**

**\* Demolition plans**

**\* Low-quality scanned drawings**

**\* Mixed raster/vector PDFs**

**\* Missing or broken wall boundaries**

**\* Manual polygon split/redraw workflow**

**\* Revising a generated polygon boundary**

**\* Addenda and drawing revisions**

**\* Preserving corrections after rerunning AI**

**\* Confidence scores or exception queues**

**\* Complete export workflow**

**\* Integration into estimating software**

**\* Waste, roll direction, seams, transitions, base, stairs, reducers, patterns, or installation labor**

**\* Independent accuracy validation**

**\---**

**\# 3\. UX patterns worth stealing**

**\#\# 1\. Let the estimator choose the extraction outputs before running AI**

**The checklist around \*\*01:35\*\* is strong. The user can request net area, wall perimeter, counts, and other quantities instead of waiting for a generic model response.**

**For your product, the flooring-specific version could be:**

**\* Room area**

**\* Base perimeter**

**\* Door/transition count**

**\* Stair tread/riser count**

**\* Open-zone detection**

**\* Finish-schedule join**

**\* Room-label extraction**

**This creates user control without forcing configuration on every polygon.**

**\#\# 2\. Preserve the drawing as the primary workspace**

**The drawing remains central while chat, classifications, and totals live in side panels. Togal does not force the estimator into a detached spreadsheet before visual review.**

**Your evidence panel should use the same principle:**

**\> Drawing on the left, room/status/material data on the right, source evidence one click away.**

**\#\# 3\. Layer isolation**

**At \*\*02:05\*\*, the presenter hides irrelevant layers and isolates net area. This is essential when AI generates many output types.**

**Your statuses—auto, review, open-zone, failed—should be individually toggleable in the same way.**

**\#\# 4\. Area and perimeter together**

**The instant display of SF and FT at \*\*02:18–02:24\*\* is directly relevant to flooring:**

**\* SF for floor finish**

**\* FT for base**

**\* Potentially perimeter minus door openings**

**This should be available on hover, not buried in a details modal.**

**\#\# 5\. Familiar desktop selection mechanics**

**At \*\*02:29–02:35\*\*, Togal uses:**

**\* Ctrl+A**

**\* Drag selection**

**\* Right-click menus**

**\* Batch operations**

**That makes the AI tool feel like conventional takeoff/CAD software instead of an unfamiliar AI application.**

**\#\# 6\. Batch assignment by semantic group**

**The user assigns all bedrooms or bathrooms at once around \*\*03:13–03:46\*\*. Even when classification is imperfect, this reduces repetitive work substantially.**

**Your schedule join can improve this pattern:**

**\> Automatically propose the material for every room sharing the same room number/name/schedule code, then let the estimator approve the group.**

**\#\# 7\. Persistent quantity tree**

**The right-side hierarchy combines:**

**\* Classification name**

**\* Count**

**\* SF**

**\* Derived units**

**\* Visibility**

**That gives constant feedback while editing.**

**Your version should add:**

**\* Verified SF**

**\* Estimated SF**

**\* Unmeasured SF**

**\* Excluded SF**

**\* Review count**

**\* Source coverage**

**\#\# 8\. Low-friction error recovery**

**The mistake at \*\*03:50–04:21\*\* does not trap the user. They can select wrong areas and delete or reassign them.**

**Your evidence-first design still needs fast editing. A defensible audit trail is not useful if every correction requires a slow form.**

**A good interaction would be:**

**\> Select polygons → press material shortcut or room-type shortcut → correction is applied immediately → evidence/change log updates in the background.**

**\#\# 9\. Show output immediately after each change**

**Totals appear to update as classifications are assigned. This provides continuous reassurance that the estimator’s edits are affecting the bid quantities.**

**\---**

**\# 4\. Weaknesses and gaps**

**\#\# A. The demo uses a highly favorable plan**

**The floor is:**

**\* Orthogonal**

**\* Repetitive**

**\* Cleanly drawn**

**\* Strongly enclosed**

**\* Composed of repeated apartment/hotel units**

**\* Mostly free of irregular curves and open zones**

**This is close to an ideal segmentation problem. The claim that the same result occurs on “any floor plan” at \*\*02:05–02:09\*\* is not supported.**

**\#\# B. The automatic takeoff looks more complete than it is proven to be**

**The full green overlay at \*\*01:53–02:05\*\* creates a strong impression of total coverage. At that zoom, it is difficult to see:**

**\* Small gaps**

**\* Boundary leakage**

**\* Duplicate polygons**

**\* Slivers**

**\* Rooms merged across openings**

**\* Areas omitted because a wall is broken**

**\* Incorrect deductions**

**No coverage report or benchmark is shown.**

**\#\# C. Classification certainty is not communicated**

**At \*\*02:39\*\*, all classified polygons receive:**

**\* A definite label**

**\* A definite color**

**\* A definite count**

**\* A definite SF total**

**The later balcony/shaft correction proves that at least some labels are wrong. There is no visible:**

**\* Confidence score**

**\* “Review recommended” state**

**\* Uncertain color treatment**

**\* Model disagreement**

**\* Rule explaining why the class was chosen**

**\#\# D. Material assignment is not schedule-driven**

**The video starts with project chat summarizing finishes, but there is no demonstrated connection between that summary and the takeoff.**

**The presenter manually decides:**

**\* Bedrooms get LVT Type 2**

**\* Bathrooms get LVT Type 3**

**\* Corridor gets carpet**

**\* Balconies get polished concrete**

**No room polygon is visibly linked to:**

**\* A room finish schedule row**

**\* A room number**

**\* A keynote**

**\* A finish legend**

**\* A specification section**

**That is the largest flooring-specific gap in the demo.**

**\#\# E. The system does not visibly reconcile completeness**

**The generated net area is around \*\*15,524 SF\*\*, while final assigned materials total around \*\*12,708 SF\*\*.**

**That difference may be correct. But the demo does not show a coverage statement such as:**

**\> 12,708 SF assigned**

**\> 2,167 SF excluded as non-flooring**

**\> 649 SF shaft void**

**\> 0 SF awaiting review**

**Without reconciliation, an estimator has to inspect categories manually to know whether the takeoff is complete.**

**\#\# F. “Cleanup is easy” is true but underspecified**

**The correction is fast, but the demo does not show whether the user:**

**\* Changes room type**

**\* Changes material only**

**\* Deletes the measurement entirely**

**\* Marks an exclusion reason**

**\* Preserves the original model output**

**\* Creates training feedback**

**Deleting a polygon can hide an AI mistake without improving auditability.**

**\#\# G. Exact totals may create false confidence**

**The software shows exact values down to individual square feet and derived unit counts. Exact arithmetic is not the same as accurate geometry.**

**The video provides no independent comparison against:**

**\* A human takeoff**

**\* CAD area**

**\* Answer-key polygons**

**\* Known schedule quantities**

**\* Tolerance thresholds**

**\#\# H. No difficult flooring scope is demonstrated**

**The demo does not address:**

**\* Roll carpet seam layout**

**\* Sheet vinyl**

**\* Broadloom waste**

**\* Pattern match**

**\* Tile layout and cuts**

**\* Cove base**

**\* Resilient base**

**\* Transitions**

**\* Stair nosing**

**\* Wall tile**

**\* Curbs**

**\* Floor prep**

**\* Moisture mitigation**

**\* Demolition**

**\* Alternates**

**\* Phasing**

**\* Material substitutions**

**\* Attic stock**

**The “flooring takeoff” shown is primarily room area assignment.**

**\#\# I. Chat grounding is partial, not fully auditable**

**One chat result shows source links, which is positive. But the longer finish answer does not visibly show a source for every bullet.**

**The presenter says the information is pulled directly from uploaded documents, but the demo does not establish:**

**\* Citation completeness**

**\* Conflict resolution**

**\* Revision precedence**

**\* Whether the answer paraphrases accurately**

**\* Whether absence means truly absent**

**\#\# J. General-purpose breadth may dilute flooring specialization**

**Togal detects sinks, tubs, doors, televisions, and other objects. That breadth is impressive, but a flooring estimator may care more about:**

**\* Finish code**

**\* Base code**

**\* Transition condition**

**\* Substrate**

**\* Adhesive**

**\* Room exclusion**

**\* Schedule evidence**

**\* Revision impact**

**General object detection is not automatically a flooring advantage.**

**\#\# K. Setup work is hidden**

**The presenter says he has built a classification library. The demo skips:**

**\* Creating materials**

**\* Adding dimensions**

**\* Pricing fields**

**\* Packaging rates**

**\* Organization templates**

**\* Naming conventions**

**\* Mapping room types to products**

**The 4.5-minute headline therefore excludes meaningful onboarding/configuration work.**

**\---**

**\# 5\. Head-to-head versus your approach**

**Your side below is based on your stated design, not a demonstrated production system.**

**| Area                                | Togal                                                               | Your proposed approach                        | Current advantage                                         |**

**| \----------------------------------- | \------------------------------------------------------------------- | \--------------------------------------------- | \--------------------------------------------------------- |**

**| Product maturity                    | Working editor and workflow demonstrated                            | Pre-launch                                    | \*\*Togal\*\*                                                 |**

**| Automatic room geometry             | Demonstrated on a favorable plan                                    | Planned dual rules/ML wall and polygon system | \*\*Togal until benchmarked\*\*                               |**

**| Editing ergonomics                  | Strong batch selection, right-click assignment, visibility controls | Not yet demonstrated                          | \*\*Togal\*\*                                                 |**

**| Multi-document project UI           | Demonstrated                                                        | Pipeline described, UI partially designed     | \*\*Togal\*\*                                                 |**

**| Project chat                        | Demonstrated with some source references                            | Not central to current pipeline               | \*\*Togal\*\*                                                 |**

**| Broad quantity types                | Areas, lines, doors, walls, counts                                  | Flooring-focused                              | \*\*Togal for breadth\*\*                                     |**

**| Flooring material determination     | Human manually maps room classes to materials                       | Planned schedule-to-room join                 | \*\*Potentially you\*\*, once proven                          |**

**| Evidence per material assignment    | Not demonstrated                                                    | Core proposed differentiator                  | \*\*Potentially you\*\*                                       |**

**| Unmeasured/failed regions           | Not visibly surfaced                                                | Planned explicit statuses                     | \*\*Potentially you\*\*                                       |**

**| Confidence/review queue             | Not shown                                                           | Planned auto/review/open-zone/failed states   | \*\*Potentially you\*\*                                       |**

**| Verified versus estimated split     | Not shown                                                           | Planned                                       | \*\*Potentially you\*\*                                       |**

**| Answer-key accuracy measurement     | Not shown                                                           | Planned benchmark system                      | \*\*Potentially you\*\*, only if representative and published |**

**| Correction capture                  | Coarse rating and manual edits shown; training linkage unknown      | Planned correction flywheel                   | \*\*Undetermined\*\*                                          |**

**| Revision/audit defensibility        | Not shown                                                           | Planned traceability                          | \*\*Potentially you\*\*                                       |**

**| Speed to visible value              | One-click geometry and rapid batch editing                          | Unknown                                       | \*\*Togal\*\*                                                 |**

**| Market credibility and distribution | User describes Togal as market leader; mature sales demo is evident | Pre-launch                                    | \*\*Togal\*\*                                                 |**

**\#\# Where Togal is genuinely ahead**

**\#\#\# Engineering**

**\* Production-grade PDF/drawing viewer**

**\* Geometry-selection model**

**\* Layer hierarchy**

**\* Batch operations**

**\* Context menus**

**\* Quantity aggregation**

**\* Multiple takeoff types**

**\* Fast rerun workflow**

**\* Integrated project chat**

**\* Material/classification hierarchy**

**\* Conventional CAD-like editing**

**These are substantial product-engineering advantages. Even if your segmentation model becomes more accurate, users may still prefer Togal if your correction interface is slower.**

**\#\#\# Data/model capability**

**The demo indicates trained models for:**

**\* Room/area extraction**

**\* Wall/door geometry**

**\* Object counts**

**\* Room semantic classification**

**The quality outside the selected plan is unknown. Still, Togal has likely accumulated real usage feedback simply by operating in market. The video itself does not prove how that feedback is used.**

**\#\#\# Distribution**

**The sales motion appears mature:**

**\* Polished product demo**

**\* Custom demonstrations on customer plans**

**\* Existing brand awareness**

**\* Broad trade applicability**

**\* A product that can be shown delivering value in minutes**

**Distribution may be harder to copy than the visible AI features.**

**\#\# Where you may be ahead**

**\#\#\# 1\. Flooring-specific source linkage**

**Togal’s flow is:**

**\> Identify room type → human assigns floor material.**

**Your intended flow is:**

**\> Identify room → find schedule row → propose material → show evidence → measure → surface uncertainty.**

**That is more aligned with how a flooring estimator defends a bid.**

**\#\#\# 2\. Honest incompleteness**

**Showing open zones, failed rooms, and unmeasured areas can be a real advantage because the principal risk is not an obvious wrong polygon. It is a room that silently disappears from the takeoff.**

**\#\#\# 3\. Quantity provenance**

**A room-level record containing:**

**\* Polygon**

**\* Area**

**\* Base perimeter**

**\* Schedule row**

**\* Finish code**

**\* Printed dimension**

**\* Model/rule source**

**\* Review history**

**would be more auditable than the demo’s classification tree.**

**\#\#\# 4\. Benchmark discipline**

**Answer-key grading could let you make narrower but more credible claims:**

**\* Percentage of rooms measured within tolerance**

**\* Percentage of total SF recovered**

**\* False-closure rate**

**\* Open-zone detection rate**

**\* Schedule material accuracy**

**\* Human correction time**

**That is better than “works on any floor plan,” provided the evaluation set is representative.**

**\#\# Skepticism your own approach still deserves**

**Your proposed advantages are not automatically real because they exist in the architecture.**

**\* \*\*Evidence traceability\*\* can become clutter that estimators ignore.**

**\* \*\*Verified versus estimated\*\* only matters if verification has a clear standard.**

**\* \*\*Answer-key accuracy\*\* can be misleading if the dataset overrepresents clean plans.**

**\* \*\*Correction flywheel\*\* requires normalized corrections, not merely event logging.**

**\* \*\*Dual rules/ML engines\*\* can increase maintenance and create conflicting outputs.**

**\* \*\*CAD-layer training data\*\* may not transfer cleanly to flattened raster permit PDFs.**

**\* \*\*Honest unmeasured regions\*\* are useful, but users may reject the product if too much remains unmeasured.**

**\* \*\*Schedule joins\*\* can fail when room names, numbers, alternates, or unit types do not align.**

**Your position should therefore be “more inspectable and flooring-specific,” not “automatically more accurate” until tested.**

**\---**

**\# 6\. What you should change now**

**\#\# Priority 0 — required before launch**

**\#\#\# 1\. Add a coverage reconciliation panel**

**This is the clearest improvement over the Togal demo.**

**For every page and project, show:**

**\* Total detected usable area**

**\* Material-assigned area**

**\* Excluded area**

**\* Open-zone area**

**\* Failed/unmeasured area**

**\* Awaiting-review area**

**\* Difference from expected/building gross area, where available**

**Example:**

**\> 48,220 SF detected**

**\> 43,870 SF assigned to flooring**

**\> 2,310 SF intentionally excluded**

**\> 1,440 SF awaiting review**

**\> 600 SF unmeasured/open**

**\> Coverage: 98.8%**

**This prevents a visually impressive colored plan from concealing omissions.**

**\#\#\# 2\. Match Togal’s batch-editing speed**

**You need, at minimum:**

**\* Ctrl+A**

**\* Shift-click**

**\* Box selection**

**\* Select all with same room type**

**\* Select all with same proposed finish**

**\* Right-click or keyboard material assignment**

**\* Bulk confirm**

**\* Bulk exclude**

**\* Undo/redo**

**Do not make evidence review require one room at a time.**

**\#\#\# 3\. Show SF and base LF directly on hover**

**Togal’s area/perimeter interaction is good. Your version should additionally show:**

**\* Gross polygon SF**

**\* Net flooring SF**

**\* Base LF**

**\* Deductions**

**\* Material**

**\* Status**

**\* Confidence**

**\* Evidence count**

**\#\#\# 4\. Make uncertainty visible on the drawing**

**Do not simply use different material colors.**

**Use a second visual channel:**

**\* Solid boundary \= confirmed**

**\* Dashed boundary \= machine-generated, awaiting review**

**\* Amber hatch \= conflicting evidence**

**\* Red/open boundary \= failed closure**

**\* Gray \= intentionally excluded**

**\* No fill \= unmeasured**

**A user should be able to distinguish material from trust status.**

**\#\#\# 5\. Build fast correction tools**

**At launch, support:**

**\* Reassign room type**

**\* Reassign material**

**\* Split polygon**

**\* Merge polygons**

**\* Redraw boundary**

**\* Mark open zone**

**\* Exclude with reason**

**\* Add missing room**

**\* Restore model output**

**\* Compare before/after**

**Every action should be quick, while the audit log happens automatically.**

**\#\#\# 6\. Add source evidence at room level**

**Selecting a room should reveal:**

**\* Finish-schedule row**

**\* Room number/name match**

**\* Relevant legend/keynote**

**\* Printed dimensions used**

**\* Scale source**

**\* Page and crop**

**\* Why the material was proposed**

**Do not require the estimator to open a separate generic chat to validate each quantity.**

**\#\#\# 7\. Require scale confirmation**

**Show:**

**\> Detected scale: 1/8" \= 1'-0"**

**\> Source: printed sheet scale**

**\> Verified against dimension: 24'-4 1/2"**

**\> Difference: 0.4%**

**The estimator should confirm once before quantities become “verified.”**

**\#\# Priority 1 — strong competitive response**

**\#\#\# 8\. Add Togal-style pre-run extraction controls**

**Let the estimator choose:**

**\* Floor SF**

**\* Base LF**

**\* Transitions**

**\* Room labels**

**\* Finish schedule**

**\* Door deductions**

**\* Stairs**

**\* Demolition**

**\* Counts**

**This makes the workflow feel deliberate and fast.**

**\#\#\# 9\. Add organization-level flooring templates**

**Templates should store:**

**\* Material codes**

**\* Product dimensions**

**\* Waste factors**

**\* Carton coverage**

**\* Roll width**

**\* Base height/type**

**\* Labor rate**

**\* Default exclusions**

**\* Schedule terminology aliases**

**Togal visibly benefits from a prebuilt library. You need the same convenience with stronger flooring semantics.**

**\#\#\# 10\. Build a project-wide source assistant, but keep it subordinate**

**A project chat is useful for:**

**\* Scope exclusions**

**\* Approved manufacturers**

**\* Installation notes**

**\* Moisture requirements**

**\* Alternates**

**\* Attic stock**

**\* Specification conflicts**

**However, every answer should cite exact pages and preferably exact regions. Do not make generic chat the core product before takeoff reliability.**

**\#\#\# 11\. Preserve corrections across reruns and revisions**

**When a new addendum arrives:**

**\* Rerun affected pages**

**\* Diff old/new geometry**

**\* Preserve unchanged confirmations**

**\* Flag changed schedule rows**

**\* Show quantities added/removed**

**\* Never silently overwrite estimator corrections**

**\#\#\# 12\. Instrument correction quality**

**Do more than capture clicks. Record:**

**\* Original prediction**

**\* Final corrected result**

**\* Correction type**

**\* Geometry delta**

**\* Material delta**

**\* Evidence used**

**\* Estimator identity**

**\* Whether correction was later reversed**

**This turns the flywheel into usable training data.**

**\#\# Claims you should prepare counters for**

**\#\#\# Against “fastest and easiest”**

**Respond with measured workflow data, not adjectives:**

**\> Median estimator review time per 50,000 SF**

**\> Percentage of SF accepted without correction**

**\> Number of unresolved rooms at export**

**\#\#\# Against “works on any floor plan”**

**Publish performance by plan category:**

**\* Clean vector**

**\* Flattened vector**

**\* Low-resolution raster**

**\* Renovation**

**\* Open office**

**\* Curved layout**

**\* Mixed-use**

**\* Multifamily**

**\* Large retail**

**\#\#\# Against “thousands of clicks saved”**

**Measure:**

**\* Manual clicks avoided**

**\* Corrections required**

**\* Total review clicks**

**\* Time from upload to exportable flooring quantity**

**\#\#\# Against broad general-purpose takeoff**

**Position specialization:**

**\> Togal recognizes many drawing objects. We focus on the flooring decisions that determine whether the bid is complete and defensible.**

**\---**

**\# 7\. What you should not copy**

**\#\# 1\. Do not use a uniform “success green” for all generated geometry**

**A completely filled plan is visually impressive, but it hides uncertainty and omission risk.**

**Your design should reward completeness honestly, not cosmetically.**

**\#\# 2\. Do not make room-type classification an unnecessary intermediate dependency**

**Togal first decides “bedroom” or “bathroom,” then the presenter manually maps that to flooring.**

**Where the finish schedule identifies rooms directly, your primary relationship should be:**

**\> Room identity → schedule finish.**

**Room type can help, but it should not override source documents.**

**\#\# 3\. Do not claim “any floor plan”**

**It creates an easy credibility failure. Use bounded claims tied to benchmarks.**

**\#\# 4\. Do not prioritize general object counting before flooring exceptions**

**Detecting televisions and cooktops looks technically broad but may not improve a flooring bid.**

**Prioritize:**

**\* Unclosed rooms**

**\* Schedule mismatches**

**\* Excluded shafts**

**\* Floor finish conflicts**

**\* Missing base**

**\* Transition boundaries**

**\* Revision changes**

**\#\# 5\. Do not rely on coarse Great/OK/Poor feedback as the correction flywheel**

**That rating tells you satisfaction, not what failed.**

**Collect structured geometry and classification corrections.**

**\#\# 6\. Do not make deletion the only way to clean bad results**

**Deletion can erase evidence of failure.**

**Use explicit states:**

**\* Excluded: elevator shaft**

**\* Not flooring scope**

**\* Duplicate**

**\* Incorrect closure**

**\* Wrong material**

**\* Wrong room match**

**\#\# 7\. Do not build every generic CAD transform before proving the core review loop**

**Flip, rotate, copy, and duplicate may be useful eventually. Split, merge, redraw, assign, exclude, and restore are more important for flooring takeoff.**

**\#\# 8\. Do not place unsupported pricing beside uncertain quantities**

**A dollar value makes a quantity feel final. Pricing should clearly inherit the quantity’s verification state.**

**Example:**

**\> $48,210 verified**

**\> $6,850 pending room review**

**\> $1,120 based on estimated/open-zone area**

**\---**

**\# 8\. Positioning and sales intelligence**

**\#\# Pricing signals**

**No actual subscription price is provided.**

**The closing call to:**

**\> Schedule a demo and send us a set of drawings**

**suggests a sales-led rather than immediately self-serve motion. That often implies:**

**\* Custom onboarding**

**\* Organization-level setup**

**\* Potentially negotiated plans**

**\* Emphasis on larger estimating teams**

**That is an inference from the sales motion, not proof of their pricing model.**

**\#\# Target customer**

**The presenter explicitly speaks as an estimator. The broader area, line, and object tools imply Togal is targeting more than flooring specialists.**

**Likely target profiles include:**

**\* General contractors**

**\* Estimating departments**

**\* Subcontractor estimators**

**\* Preconstruction teams**

**\* Organizations performing multiple takeoff types**

**The video’s flooring workflow is probably one use case within a general-purpose takeoff platform.**

**\#\# Onboarding friction**

**Visible or implied setup includes:**

**\* Uploading and organizing large drawing sets**

**\* Allowing documents to process**

**\* Building a classification library**

**\* Creating flooring material types**

**\* Configuring product dimensions**

**\* Possibly configuring pricing**

**\* Confirming scale**

**\* Learning the quantity hierarchy**

**The demo avoids this setup by starting with a populated project and prebuilt library.**

**\#\# Integration claims**

**No external integration is demonstrated.**

**Visible controls suggest export capabilities, but the video does not show:**

**\* Excel**

**\* Google Sheets**

**\* Procore**

**\* Autodesk**

**\* Sage**

**\* estimating platforms**

**\* API access**

**\* bid templates**

**\* accounting or procurement handoff**

**Treat export/integration capability as unknown until tested.**

**\#\# Friction in their workflow**

**The estimator still must:**

**\* Interpret the scope**

**\* Decide which room classes get which material**

**\* Catch mixed classifications**

**\* Exclude true shafts/non-flooring areas**

**\* Judge whether every room was captured**

**\* Decide whether final totals are complete**

**Togal reduces geometry labor more convincingly than it automates flooring scope judgment.**

**\#\# One-sentence competitive pitch**

**\> \*\*Togal gives you fast takeoff geometry; we give you a flooring quantity you can defend—every room tied to the finish schedule and drawing evidence, with uncertain and unmeasured areas surfaced before they reach the bid.\*\***

**A more conversational estimator version:**

**\> \*\*Togal colors the plan fast; we show you which numbers are actually supported, where each finish came from, and exactly what still needs your review.\*\***

**\---**

**\# 9\. Open questions to investigate**

**\#\# Product behavior**

**1\. How is scale detected, calibrated, and verified?**

**2\. What happens when printed scale and dimension checks disagree?**

**3\. Does Re-Togal preserve manual edits?**

**4\. Can a user split, merge, or redraw an incorrect polygon?**

**5\. Does AutoClassify expose confidence scores internally?**

**6\. Can users filter only low-confidence predictions?**

**7\. Are missing/unclosed areas explicitly surfaced?**

**8\. Can the system reconcile measured versus assigned versus excluded SF?**

**9\. Can it automatically join room finish schedules to room polygons?**

**10\. Can it distinguish room type from material finish without manual mapping?**

**11\. How does it handle unit plans repeated across multiple floors?**

**12\. Can it copy confirmed takeoffs between repeated unit types?**

**13\. How are alternates and addenda handled?**

**14\. Can Compare identify quantity changes between drawing revisions?**

**15\. Are deleted features retained in an audit log?**

**\#\# Accuracy and model evidence**

**16\. What datasets are used for room and wall detection?**

**17\. Does Togal publish precision/recall or area-error metrics?**

**18\. What percentage of generated geometry typically needs correction?**

**19\. Does it evaluate total-SF recovery or only individual polygon accuracy?**

**20\. How does it perform on raster scans and low-resolution permit sets?**

**21\. How does it handle open-plan rooms, glass walls, railings, curves, and partial-height partitions?**

**22\. Are semantic classification corrections used to retrain organization-specific or global models?**

**23\. Does the Great/OK/Poor feedback connect to the exact model output?**

**24\. Are chat answers evaluated separately from geometric takeoff accuracy?**

**\#\# Flooring-specific capability**

**25\. Does Togal support base LF with doorway deductions?**

**26\. Roll goods, seam planning, and pattern match?**

**27\. Waste factors by room/material?**

**28\. Cartons, pieces, and attic stock?**

**29\. Transitions and reducer counts?**

**30\. Wall tile and cove base?**

**31\. Stairs, treads, risers, and nosings?**

**32\. Demolition and floor-prep quantities?**

**33\. Material alternates and allowances?**

**34\. Substrate or moisture-system scope?**

**35\. Room-by-room schedule traceability?**

**\#\# Commercial questions**

**36\. Actual pricing and minimum contract term**

**37\. Seat-based versus usage-based billing**

**38\. Page, project, or storage limits**

**39\. Whether trial access is available without a sales call**

**40\. Onboarding fees**

**41\. Classification-library setup assistance**

**42\. Enterprise security and data retention**

**43\. API availability**

**44\. Export formats and estimating integrations**

**45\. Typical processing time for a complete 300–500-page set**

**46\. Customer support response and implementation time**

**\#\# Sources worth investigating next**

**\* Product trial using the same difficult test set you plan to benchmark**

**\* Customer review sites, focusing on correction time rather than general satisfaction**

**\* YouTube demos involving renovation, industrial, healthcare, or irregular plans**

**\* Togal patent filings related to segmentation, classification, and measurement**

**\* Togal technical blogs and release notes**

**\* Webinars showing actual estimator workflows rather than marketing demos**

**\* Forums or trade groups discussing false positives, scale problems, or export limitations**

**\* Historical product videos to see which features have remained “demo-only”**

**\* Terms, pricing proposals, and implementation documentation obtained through a sales demo**

**\#\# Bottom line**

**Togal should not be treated as a weak black-box competitor. The demo shows a serious product with a mature editing environment and a practical human-in-the-loop workflow.**

**But the video also reveals the boundary of its automation:**

**\* Geometry is automatic**

**\* Room classification is imperfect**

**\* Material mapping is largely manual**

**\* Final completeness depends on estimator review**

**\* Quantity evidence and uncertainty are not visibly first-class concepts**

**Your best opportunity is not to imitate the green one-click result. It is to combine comparable speed and batch-editing ergonomics with a stronger answer to the estimator’s real question:**

**\> \*\*Can I trust that every flooring area is accounted for, assigned to the correct material, and traceable to the documents I am bidding from?\*\***

