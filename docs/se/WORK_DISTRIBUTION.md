# Creature Collector (GitHost): work distribution and syllabus guide

Registered project name: **GitHost**. The software is the game **Creature Collector**. Any player's laptop can **host** a battle with no server, and the project is developed and versioned with **Git**. The Git branch for this evaluation is `creature-collector(githost)`.

For the team only. This guide shows:
- who owns which part of the code;
- who presents which slides;
- for every syllabus topic, a definition and where we applied and tested it.

Report = `docs/se/CreatureCollector-SE-Report.pdf`. Slides = `docs/se/CreatureCollector-SE.pdf` (32 slides).

## 1. Who does what

| Member | Owns in the code | Presents slides | Syllabus topics to master |
|---|---|---|---|
| **Parth Virendra Saraf** (IIT2025024) | Game rules and battles: `src/model/creature.py`, `move.py`, `move_effect.py`, `status.py`, `battle.py`, `battle_ai.py`, `damage.py`, `events.py`, `type_chart.py` | 1–4, 9–12, 18, 20, 21 | Software characteristics, SE principles, UML, functional vs OO design, cohesion and coupling, SDLC models, metrics, COCOMO |
| **Subala Periyasami** (IIT2025070) | World, story, items and saving: `src/model/entities.py`, `world.py`, `story.py`, `trainer.py`, `item.py`, `bag.py`, `shop.py`, `game_state.py`, `src/save_manager.py`, `src/data_loader.py`, `data/` | 5–8, 14–17, 25–26 | SRS, elicitation, requirements analysis, design decisions, SA/SD, DFDs, structure chart, quality assurance, reliability, ISO 9000, CMM |
| **Usmani Areeb** (IIT2025085) | Screens, networking and testing: `src/ui/`, `src/net/`, `src/model/link_battle.py`, `tests/` | 13, 19, 22–24, 27–31 | Architecture, client-server, testing levels and strategies, verification and validation, risk management, maintenance, configuration management, reverse and re-engineering |

**Live demo (slide 31):**
- Subala: steps 1–3 (new game, wild battle, the shop).
- Parth: step 4 (the gym battle).
- Usmani: step 5 (the link battle).

Each person should be able to open their own files and explain one class from them.

## 2. Syllabus coverage

Each row gives:
- the syllabus term;
- a one-line definition you can say in the viva;
- where and how we applied it;
- how it was tested or what proves it;
- where it is in the report (§) and slides.

### Unit 1: Introduction to software engineering

| Term | Definition | Where and how in our project | Tested / evidence | Report | Slide |
|---|---|---|---|---|---|
| Software characteristics | Software is developed, not manufactured; it doesn't wear out but deteriorates as it is changed | We designed for safe change: content in JSON, new behaviour as subclasses | 216 tests rerun after every change | §1.4 | 4 |
| Software components | Self-contained parts with a clear interface | Four modules: data, game rules (`src/model`), network (`src/net`), screens (`src/ui`) | `test_model_layer_has_zero_pygame_imports` keeps them separate | §5.1 | 13 |
| Software applications | The kind of software built | An interactive game application with networked play | — | §1.1 | 2–3 |
| SE principles | Abstraction, modularity, separation of concerns, anticipation of change, incremental development, rigour | Abstract classes; four modules; rules never draw; JSON content; nine milestones; a test for every requirement | Test suite, Git history | §1.4 | 4 |
| Software metrics and measurement | Quantities that describe software or its process | Lines of code per module, import counts between modules, defect counts, test pass rate | Counted from the source | §9.4, §5.7, §8.1 | 21, 18, 26 |
| Monitoring and control | Tracking progress against a plan and correcting course | Milestones M1–M9, each gated by "all tests pass and committed" | Git log dates | §9.1, §9.6 | 20, 21 |
| SDLC | The phases from requirements to maintenance | We went through every phase; each has a report section | The report structure itself | §2–§10 | 5–30 |
| SDLC models (and why not others) | Waterfall, prototyping, iterative and incremental, spiral, agile | **Iterative and incremental**: one feature per iteration. Waterfall rejected because requirements grew; spiral was too heavy | 9 milestones with a working game each time | §6.2 | 20 |
| Recent developments in models | Agile, DevOps, continuous integration | Our short iterations are close to agile; CI is future work | — | §6.2, §11.2 | 20, 30 |

### Unit 2: Requirements, modelling and architecture

| Term | Definition | Where and how in our project | Tested / evidence | Report | Slide |
|---|---|---|---|---|---|
| Elicitation techniques | Ways of finding requirements: interviews, brainstorming, prototyping, document analysis, observation | Brainstorming, domain analysis of existing games, the prototype, the course brief, use cases, field feedback | The 14 prototype defects became requirements | §2.5 | 7 |
| Requirements analysis | Turning raw needs into clear, testable requirements | 13 functional (FR1–FR13) and 9 non-functional (NFR1–NFR9) requirements, stakeholders, constraints | Each FR/NFR maps to test cases TC1–TC20 | §2, §3 | 5–8 |
| SRS | The document that states what the system must do | Report §2: users, FRs, NFRs, constraints and assumptions | — | §2 | 5–6 |
| Modelling and architecture | Describing the system's structure before and while building it | Layered architecture: data → rules → screens, plus network | Import counts; no-pygame test | §5.1 | 13 |
| UML diagrams | Standard object-oriented models | Use-case, class, sequence, activity and state diagrams | Diagrams match the real classes (`Battle`, `BattleState`) | §3–§4 | 8–12 |
| Functional vs object-oriented design | Functional design splits the system into functions over data; OO design splits it into objects with data and behaviour | Analysed with DFDs (functional), built with classes (OO) | — | §5.6 | 18 |
| Design specification | A precise statement of the design | Module table (responsibility and "must not"), class and state diagrams, design decisions with reasons | — | §5.1–5.3 | 13–14 |
| Cohesion | How strongly the parts of one module belong together; functional cohesion is best | `DamageCalculator` only computes damage; `Shop` only buys and sells; `SaveManager` only saves | Each has its own focused tests | §5.7 | 18 |
| Coupling | How much modules depend on each other; data coupling is weakest (best) | Modules pass plain data (`BattleEvent`, JSON). Imports: screens→rules 23, network→rules 5, rules→anything above 0 | `test_model_layer_has_zero_pygame_imports` | §5.7 | 18 |
| SA/SD methodology | Structured analysis (DFDs) followed by structured design (structure charts) | Level-0 and level-1 DFDs, then a structure chart by transform analysis | — | §5.4–5.5 | 15–17 |
| Structured analysis | Modelling a system by the flow of data through processes | Six processes, two data stores (D1 game data, D2 save file) | — | §5.4 | 15–16 |
| Data flow diagrams | Processes (circles), external entities (boxes), data stores (open boxes), data flows (arrows) | Level 0: the game, Player, Friend's game, Content maintainer. Level 1: load data, input/screens, explore, battle, save, link | — | §5.4 | 15–16 |
| DFD → structure chart | Transform analysis: split the DFD into input (afferent), central transform and output (efferent) | `GameEngine.run` → `handle_event` (afferent), `update` → `Explorer.step`, `Battle.execute_move` (transform), `draw` (efferent) | — | §5.5 | 17 |

### Unit 3: Project planning, reliability and quality

| Term | Definition | Where and how in our project | Tested / evidence | Report | Slide |
|---|---|---|---|---|---|
| Project scheduling | Ordering work into milestones with dates | M1–M9 with dates from Git (17–18 Nov 2026) | Git log | §9.1 | 20 |
| Size metrics | Measuring size, usually in lines of code (LOC/KLOC) | 7,590 delivered lines (rules 2,944, screens 3,881, network 551, other 214); tests 3,003 | Counted from the source | §9.4 | 21 |
| COCOMO | Estimates effort from size. Basic organic mode: E = 2.4·KLOC^1.05, T = 2.5·E^0.38 | KLOC 7.59 → 20.2 person-months, 7.8 months, 2.6 people. Real schedule was shorter because we re-engineered and reused a prototype | Worked calculation | §9.5 | 21 |
| Risk management | Identify risks, judge their impact, plan mitigation | Risk table: blocked Wi-Fi, firewall, version mismatch, scope creep, regressions | Mitigations are real features (hotspot advice, fingerprint check, test suite) | §9.3 | 27 |
| Reliability issues | What can make software fail in use | Crashes mid-save, network drops, mismatched copies, platform differences | TC8, TC9, TC14, TC15, disconnect tests | §8 | 25 |
| Reliability metrics | MTTF, MTBF, defect counts, failure rate | Defects: 14 in inspection, 2 in the field, 0 open; 216/216 tests pass. MTTF/MTBF not measured: no usage data yet | Test runs | §8.1 | 26 |
| Reliability models | Predict future failures from past ones, e.g. Jelinski–Moranda | Not applied: needs failure-time data; listed as future work | — | §8.1 | 26 |
| Software quality / QA | Meeting requirements; reliability, maintainability, security, usability, performance, portability | Quality table with evidence for each attribute | Linked test cases | §8 | 25 |
| ISO 9000 | Standards for a quality management system: documented process, records, reviews, corrective action | We follow the ideas (SRS, Git records, inspection, a test for every fix); not certified | — | §8.2 | 26 |
| SEI CMM | Five maturity levels: Initial, Repeatable, Defined, Managed, Optimizing | Self-assessed: level 2 practices, part of level 3. No formal appraisal | — | §8.3 | 26 |
| Client-server development | A server provides a service that clients request | Link battle: the host is the server and decides results; the guest is the client. No central server | `test_handshake_and_a_turn_over_tcp`, `test_full_battle_both_games_agree` | §5.8 | 19 |

### Unit 4: Verification, validation and maintenance

| Term | Definition | Where and how in our project | Tested / evidence | Report | Slide |
|---|---|---|---|---|---|
| Verification vs validation | Verification: building the product right. Validation: building the right product | Inspection, test plan and white-box tests (verification); black-box, alpha and field tests (validation) | — | §7.4 | 24 |
| Code inspection | Reviewing code by reading it, without running it | Read the first prototype line by line: 14 defects found | Each defect has a regression test (`test_bug_regressions.py`) | §7.3, §7.4 | 24 |
| Test plan | What will be tested, how and when | Strategy: unit, integration, system; all tests run after every change | — | §7.1 | 22 |
| Test case specification | Each test with ID, input or steps, expected result | TC1–TC20 with level, expected result, test file, result | All pass | §7.2 | 23 |
| Levels of testing | Unit, integration, system, acceptance | Unit: classes; integration: shop screen, link over TCP; system: whole game and link battle | 216 automated tests | §7.1 | 22 |
| Top-down vs bottom-up integration | Bottom-up: test low-level modules first. Top-down: test from the top, with stubs for missing parts | Bottom-up for rules → screens. Top-down for the network, with `MemoryConnection` as a stub | `tests/test_link_network.py` uses the stub | §7.4 | 24 |
| Alpha and beta testing | Alpha: by the developers in-house. Beta: by users in real conditions | Alpha: team played the whole game each milestone. Beta-style: two real laptops (found the line-ending defect) | TC15 added after the field test | §7.4 | 24 |
| System testing and debugging | Testing the complete system; finding and fixing the cause of a failure | Whole-game tests; debugging: reproduce → isolate → fix → regression test | TC16–TC20 | §7.3–7.4 | 23–24 |
| Functional (black-box) testing | Testing against requirements without looking at the code | e.g. "buying without enough money is refused" from FR8 | TC4–TC6 | §7.4 | 24 |
| Structural (white-box) testing | Testing internal paths, using knowledge of the code | Sleep wearing off, a creature with no moves left, a save failing half-way | `test_bug_regressions.py`, TC8 | §7.4 | 24 |
| Software testing strategies | The overall approach to testing | Test-first for defects; every change runs all tests; screens tested with simulated keys; no-overflow checks | — | §7.1 | 22 |
| Software maintenance and reuse | Changing software after delivery; building from existing parts | Corrective, adaptive, perfective, preventive examples. Reuse: `LinkBattle` reuses `Battle`; the link screen reuses the battle screen | — | §10, §10.4 | 28–29 |
| Structured vs unstructured maintenance | Structured: start from design documents and tests. Unstructured: only code exists | Ours is structured: SRS, UML, decisions and tests exist | — | §10.2 | 29 |
| Maintenance models | Quick-fix, iterative enhancement, reuse-oriented | Iterative enhancement, with reuse where it fits | — | §10.1 | 29 |
| Configuration management | Identifying, controlling and recording versions of every artefact | Git for every change; versioned save files; `PROTOCOL_VERSION` and data fingerprint (`src/net/protocol.py`); `requirements.txt` | `test_different_versions_are_refused`, save version tests in `test_errors.py` | §10.3 | 29 |
| Reverse engineering | Recovering design information from existing code | Read the prototype's code to recover its design and defects (milestone M1, `docs/PLAN.md`) | — | §10.4 | 29 |
| Software re-engineering | Restructuring existing software to improve it, keeping its behaviour | Restructured the prototype into clean classes; separated rules from graphics before adding features | Old tests kept passing during the restructuring | §10.4 | 29 |

## 3. Questions to expect, by owner

- **Parth:**
  - Why iterative and incremental, not waterfall?
  - Show cohesion and coupling in the code.
  - How did you calculate COCOMO, and why does the estimate differ from reality?
  - Walk through the state diagram.
- **Subala:**
  - How did you gather requirements?
  - Explain the level-1 DFD and how you got the structure chart from it.
  - What does ISO 9000 require, and do you meet it?
  - What CMM level are you, and why?
- **Usmani:**
  - Is the link battle client-server or peer-to-peer?
  - Top-down or bottom-up integration, and what was the stub?
  - What's the difference between verification and validation?
  - Tell us about the defect found on real laptops.
  - How do you do configuration management?

## 4. Be honest about these

If asked, say these plainly:
- MTTF/MTBF and reliability models were **not** measured: there is no usage data yet.
- Not ISO-certified; CMM level is a **self-assessment**.
- The Git history covers only 17–18 November: the prototype existed earlier, and the commits record the structured rebuild.
- Beta testing was a field test on two laptops, not a public beta.
