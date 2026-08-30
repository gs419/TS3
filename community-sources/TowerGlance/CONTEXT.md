# TowerGlance

TowerGlance presents the local operational picture of a Tower! Simulator 3 session in an independent local webview and may project explicitly selected stripboard placement back into that session.

## Language

**Operational Session**:
One continuous Tower! Simulator 3 run at one airport whose observed and derived operational state TowerGlance presents; a TowerGlance instance follows at most one such live run. Returning to the game menu ends it, and a later run is a new Operational Session rather than a continuation.
_Avoid_: Browser session, user session

**Ready Operational Session**:
An Operational Session for which game-derived evidence confirms an active run and its airport. Individual TowerGlance capabilities may still be unavailable according to their Source Health.
_Avoid_: Fully healthy session, all sources ready

**Quick Play Session**:
An Operational Session started through Tower! Simulator 3 Quick Play with a selected locally available schedule database and time window.
_Avoid_: Scheduled Session, regular session

**Career Challenge**:
An Operational Session started through Tower! Simulator 3 Career from a challenge-defined time window, traffic set, and optional operating conditions or restrictions.
_Avoid_: Career session, career schedule

**Flight**:
One planned or game-observed aircraft movement within an Operational Session whose identity TowerGlance follows consistently across its lifecycle. A schedule occurrence and live game observations describe the same Flight only when admitted evidence establishes their continuity.
_Avoid_: Schedule row, callsign identity, cross-session flight

**Flight Identity**:
The Operational Session-scoped identity TowerGlance assigns to one Flight occurrence and preserves across its lifecycle once admitted evidence establishes it. It never carries across sessions and is not equal to any one source field.
_Avoid_: Callsign identity, schedule-row ID, persistent Flight ID

**Flight Identity Evidence**:
Admitted facts that uniquely establish or continue a Flight Identity within its applicable session and candidate set. Callsign and flight number are primary and may suffice when unique; collisions require corroborating schedule and live facts.
_Avoid_: Globally unique callsign, mandatory hidden game ID

**Flight Identity Continuity**:
The persistence of a confirmed Flight Identity across later observations while admitted source relationships prove the same occurrence. Fact changes or lost evidence never trigger silent rematching; ambiguity remains until authoritative evidence establishes continuity or a lifecycle end and new occurrence.
_Avoid_: Continuous rematching, latest callsign wins, permanent source index

**Aircraft**:
The physical game-observed manifestation of a Flight once Tower! Simulator 3 instantiates it. In v1 it has no persistent domain identity independent of its Flight; game source identifiers provide correlation evidence only.
_Avoid_: Flight, persistent airframe

**Aircraft Type**:
A game-owned aircraft type resolved from the applicable Aircraft definition. Its planned value remains a Schedule Fact, while its game-observed value is authoritative for the manifested Aircraft; a conflict rejects Flight Correlation rather than overwriting either fact.
_Avoid_: Aircraft identity, Aircraft category, inferred type

**Regional Aircraft**:
An Aircraft whose game-owned type definition explicitly assigns Tower! Simulator 3's `REGIONAL_JET` category. The category is independent of weight class and physical dimensions and does not by itself establish Flight service, route, wake category, or other unverified behaviour.
_Avoid_: Regional Flight, assumed small aircraft

**Wake Turbulence Category**:
A source-evidenced Aircraft characteristic representing the wake category explicitly supplied by game-owned data. Scheduled and game-observed values remain separate facts, and TowerGlance does not infer the category from other Aircraft characteristics.
_Avoid_: Aircraft category, inferred weight class

**Planned Aircraft Assignment**:
A Flight's Schedule Facts describing its intended aircraft type and, when supplied, registration before Aircraft instantiation. It is not an Aircraft and remains available after Operational Facts describe the observed Aircraft.
_Avoid_: Planned Aircraft, scheduled airframe

**Aircraft Registration**:
An optional Schedule Fact identifying the registration assigned to a Flight's planned aircraft. It remains planned after Aircraft instantiation and is neither Flight Identity nor an independent Aircraft identity; a future authoritative live value would remain a separate Operational Fact.
_Avoid_: Flight ID, persistent Aircraft ID, assumed live registration

**Terminal**:
A named static grouping of Gates in game-owned airport data that may define operator eligibility. It is airport configuration rather than a physical resource occupied by one Aircraft.
_Avoid_: Gate, occupied terminal, current assignment

**Gate**:
A concrete airport resource at which an Aircraft may be parked. Its relationship to a Terminal supplies terminal context but does not itself prove assignment or occupancy.
_Avoid_: Terminal, gate eligibility, parking area in general

**Terminal Eligibility**:
A static game-owned relationship permitting an operator to use a Terminal. It does not establish a current Gate Assignment or Terminal association and never proves Resource Occupancy.
_Avoid_: Terminal Assignment, Gate Assignment, occupancy

**Gate Assignment**:
An Operational Assignment directing a Flight or Aircraft to a Gate. It may establish its Terminal context through that Gate but does not prove that the Aircraft physically occupies the Gate.
_Avoid_: Gate Occupancy, Terminal Eligibility

**Operational Assignment**:
A game-derived association directing a Flight or Aircraft to use a concrete airport resource such as a Gate or runway. Eligibility or assignment does not establish physical occupancy.
_Avoid_: Resource Occupancy, static permission

**Resource Occupancy**:
The authoritative current physical occupation of an airport resource by an Aircraft, independent of its Flight's lifecycle phase. It may outlast an Ended Flight but transfers exclusively when authoritative game evidence establishes that the game object now manifests a new Flight occurrence.
_Avoid_: Assigned resource, permitted resource

**Planned Phase**:
The Flight lifecycle phase before it becomes controller-interactive. It includes schedule-only awareness and game-instantiated but non-interactive presence; a Scheduled Milestone may occur during this phase.
_Avoid_: Scheduled phase, inactive status

**Live Phase**:
The Flight lifecycle phase after authoritative game evidence establishes controller-interactive presence and before authoritative end evidence.
_Avoid_: Game-present phase, visible-strip phase

**Ended Phase**:
The terminal Flight lifecycle phase after authoritative game evidence establishes that its operational movement is over.
_Avoid_: Missing phase, removed-from-view phase

**Cancelled Flight**:
A Flight that terminates from the Planned Phase on explicit authoritative cancellation evidence without entering the Live Phase. Lateness or unobserved presence does not make a Flight cancelled.
_Avoid_: Missing Flight, late Flight

**Scheduled Flight**:
A Flight for which the accepted Traffic Schedule Source supplies one admitted planned occurrence. This provenance classification persists throughout the Flight lifecycle and is independent of traffic category.
_Avoid_: Planned Flight, schedule row

**Unscheduled Flight**:
A game-observed Flight for which authoritative complete evidence proves that no planned occurrence exists in the applicable Traffic Schedule Source. Missing, unavailable, or ambiguous schedule evidence never makes a Flight unscheduled.
_Avoid_: Unmatched Flight, unknown schedule relationship

**Flight Direction**:
A Flight's movement relative to the Operational Session airport: Arrival or Departure. It is independent of schedule provenance, lifecycle phase, and Traffic Classification.
_Avoid_: Arrival type, traffic category

**Flight Origin**:
The airport or location from which one Flight occurrence begins. Its accepted schedule value is planned identity evidence; once game-observed, the game-derived value is authoritative for that Flight.
_Avoid_: Previous position, current location

**Flight Destination**:
The airport or location at which one Flight occurrence is intended to end. Its accepted schedule value is planned identity evidence; once game-observed, the game-derived value is authoritative for that Flight.
_Avoid_: Assigned runway, current target

**Traffic Classification**:
A source-evidenced label on one defined semantic axis that describes a Flight. Labels from different data families or unproven axes are not collapsed into one exclusive traffic type.
_Avoid_: Universal traffic-type enum, scheduled category

**Airline Flight**:
A Flight whose game-owned planned occurrence supplies a valid airline and operator relationship. Every Airline Flight has exactly one TowerGlance service classification: Passenger Flight or Cargo Flight.
_Avoid_: Commercial Flight, non-GA Flight

**Passenger Flight**:
An Airline Flight without an explicit game-owned cargo classification. It is the default TowerGlance airline service class and does not imply that the aircraft carries no belly cargo.
_Avoid_: Commercial Flight, cargo-free Flight

**Cargo Flight**:
An Airline Flight explicitly classified by game-owned evidence as operating a cargo service. It remains independent of schedule provenance, Flight Direction, other Traffic Classifications, and Aircraft characteristics.
_Avoid_: Cargo aircraft, inferred cargo

**VFR Flight**:
A Flight explicitly classified by game-owned evidence as operating under visual flight rules. It may be local or have different endpoints and is independent of schedule provenance and Flight Direction.
_Avoid_: Local Flight, Unscheduled Flight

**Local Flight**:
A VFR Flight whose Flight Origin and Flight Destination are the same airport. It describes the endpoint relationship, not the route or pattern actually flown.
_Avoid_: Pattern Flight, any VFR Flight

**General Aviation Flight**:
A Flight explicitly classified as general aviation by game-owned evidence, including an admitted planned occurrence from the game's General Aviation data. It may also be Scheduled, VFR, or Local and has an independent Flight Direction.
_Avoid_: Unscheduled Flight, VFR Flight, Local Flight

**Schedule Fact**:
A Normalized Fact about a Flight supplied by its accepted Traffic Schedule Source. It retains its planned value and provenance independently of later Operational Facts.
_Avoid_: Current value, fallback value

**Operational Fact**:
A Normalized Fact about a Flight supplied by an admitted operational game source. It neither overwrites nor inherits a Schedule Fact; missing operational evidence remains explicit.
_Avoid_: Merged value, assumed actual value

**Scheduled Milestone**:
The lifecycle event to which a Flight's Scheduled Time refers. Times for different milestones, such as first game presence and landing, are not interchangeable.
_Avoid_: Generic arrival, assumed landing

**Inbound Operational Entry**:
The Scheduled Milestone for an Arrival at which the Flight is due to gain its first authoritative operational game presence. Later controller contact and landing are different milestones.
_Avoid_: Arrival time, contact time, landing time

**Ready for Pushback**:
The Scheduled Milestone for a Departure at which the Flight is due to enter controller contact requesting pushback. It does not mean physical pushback, off-block, runway departure, or take-off.
_Avoid_: Departure time, off-block time, take-off time

**Scheduled Time**:
A Schedule Fact stating when a Scheduled Milestone is planned to occur.
_Avoid_: Current time, estimated time

**Estimated Time**:
An Operational Fact or Derived Fact stating when a Scheduled Milestone is currently expected, supported only by explicit operational evidence or a verified derivation.
_Avoid_: Assumed time, scheduled-time fallback

**Actual Time**:
An Operational Fact stating the Operational Session time at which a Scheduled Milestone occurred. It is a point only when the game supplies a native event time; otherwise it is the bounded interval between the last authoritative observation before occurrence and the first authoritative observation after occurrence.
_Avoid_: Receipt time, estimated time, exact first-observation time

**Delay**:
A Derived Fact measuring how late a Scheduled Milestone is against its Scheduled Time: against current Operational Session time while its non-occurrence is authoritatively known, or against Actual Time once it occurs. Delay retains any uncertainty interval present in Actual Time. If non-occurrence cannot be known reliably, Delay is unknown; different milestones are never compared.
_Avoid_: Time since any schedule value, landing delay by default

**Official Airport**:
An airport package supplied with Tower! Simulator 3 or through a locally installed official airport DLC and eligible for capability-specific verification against TowerGlance's validated official-airport standard.
_Avoid_: Supported airport, known airport

**Recovery Snapshot**:
A TowerGlance-owned local copy of the last confirmed state for an identifiable Operational Session, shown only while that session's continuity remains possible during a temporary source loss. It remains stale with visible age and uncertainty and cannot drive automation or writes; confirmed session end discards it, and only newer authoritative information from the proven same session supersedes it.
_Avoid_: Browser cache, authoritative game data

**Stripboard Mode**:
The user-selected policy by which TowerGlance advances Game-backed Strip Positions and maintains order across its entire external stripboard. A stripboard uses either Automatic Stripboard Mode or Manual Stripboard Mode.
_Avoid_: Automation setting

**Game-backed Strip Position**:
The current operational block recorded for a strip in Tower! Simulator 3 so TowerGlance and the in-game board can present the same placement. It records board placement, not lifecycle state, operational correctness, or the strip's order within that block.
_Avoid_: TowerGlance-only position, strip order

**Automatic Stripboard Mode**:
A Stripboard Mode in which TowerGlance derives when strips should move between operational blocks and records their Game-backed Strip Positions. The user may correct a position or its TowerGlance order without leaving this mode.
_Avoid_: Fully automatic board

**Manual Stripboard Mode**:
A Stripboard Mode in which the user controls Game-backed Strip Positions and strip order and TowerGlance does not automatically move existing strips between operational blocks.
_Avoid_: Manual override

**Manual Correction**:
A user-directed change to one Game-backed Strip Position or to its TowerGlance order while the stripboard remains in Automatic Stripboard Mode. Its precedence and release rules are part of the automatic-board policy rather than a separate Stripboard Mode.
_Avoid_: Manual mode, game-board change

**ADIRS**:
The Tower! Simulator 3 term observed in game-owned local data for an airport-surface display. TowerGlance adopts ADIRS for its corresponding live view of an airport layout and the aircraft presented on it.
_Avoid_: Airport Map

**Traffic Schedule**:
The Operational Session-scoped projection of Flights admitted from the known Schedule Horizon or game observation, regardless of schedule provenance. It carries one correlated Flight across the Planned and Live Phases; the Traffic Schedule Source supplies Schedule Facts but does not define the projection's entire membership.
_Avoid_: Schedule source, schedule-row list, Flight update list

**Traffic Schedule Membership**:
The inclusion of a Flight in the Traffic Schedule from its first admission until authoritative evidence establishes its Ended Phase or cancellation. Passing its Scheduled Time, movement of the Schedule Horizon, or missing live evidence does not end membership.
_Avoid_: Current horizon membership, timeout removal

**Traffic Schedule Source**:
The game-owned Operational Session configuration that identifies the selected local database profile and resolves its applicable planned-traffic file set through the game's per-file selection rules. Quick Play and Career share the profile-selection rule but select their applicable main schedule variant; candidate discovery, an assumed default, or partial live-traffic correlation does not establish this source.
_Avoid_: Session mode, assumed default schedule, best-matching schedule

**Schedule Horizon**:
The future interval for which Tower! Simulator 3 has made traffic information available to TowerGlance. It may vary by session and game settings such as schedule preload and is not a fixed duration promised by TowerGlance.
_Avoid_: Forecast window

**Source Health**:
TowerGlance's assessment of the availability, continuity, freshness, and successful interpretation of one local Tower! Simulator 3 information source. A successful current observation is fresh even when its values are unchanged; Source Health does not imply that the entire Operational Session is healthy.
_Avoid_: Connection status, overall health

**Source Authority Rule**:
The rule assigning each normalized fact category to one game-derived source or an explicit combination that together directly reports every required fact; its authority stops at those reported semantics and does not prove downstream intent, effect, or state. TowerGlance defines the rule and any precedence; new required facts or source behaviour reopen the affected rule and verification, while supplementary and recovered sources cannot become authoritative implicitly.
_Avoid_: Global source priority, best-effort merge

**Normalized Fact**:
A TowerGlance representation of one observed or derived fact that retains its value or explicit absence, source provenance, observation time or order, Operational Session context, and applied Source Authority Rule. It distinguishes explicit empty, not configured, unknown, unavailable, ambiguous, and stale or recovered states without inventing a default or assumed state.
_Avoid_: Merged value, best guess

**Derived Fact**:
A Normalized Fact produced by a verified deterministic TowerGlance rule from every required authoritative input applicable to the same Operational Session context, retaining the complete input provenance and applied rule. Its authority is limited to the semantics entailed by those inputs, and it cannot become current and certain when a required input is unknown, unavailable, ambiguous, or stale or recovered.
_Avoid_: Inferred truth, heuristic fact, upgraded evidence

**Ambiguous Fact**:
A Normalized Fact for which two admitted authority sources report conflicting values within the same applicable Operational Session context. It preserves every conflicting value and its provenance and cannot drive affected automatic behaviour unless an explicit category-specific precedence rule resolves the conflict.
_Avoid_: Unknown fact, unavailable fact, latest value wins

**Unknown Fact**:
An applicable Normalized Fact for which authoritative evidence has not yet established either a value or explicit absence. It remains unknown rather than receiving a default, estimate, or value from insufficient evidence.
_Avoid_: Unavailable fact, explicitly absent fact, assumed value

**Unavailable Fact**:
An applicable Normalized Fact whose configured authoritative source cannot currently be accessed, validated, or interpreted reliably enough to supply it. A prior value may remain visible only under the applicable stale or recovery semantics.
_Avoid_: Unknown fact, not configured, explicitly absent fact

**Explicitly Absent Fact**:
An applicable Normalized Fact for which its authoritative source validly establishes that no value or relationship exists. It is known absence rather than an unknown, unavailable, or unconfigured state.
_Avoid_: Empty string default, unknown fact, unavailable fact

**Not Configured**:
A Normalized Fact state showing that a supported optional game capability is deliberately disabled or has no configured source in the applicable Operational Session. It is not unavailable: an expected configured source that cannot be read or satisfied is unavailable.
_Avoid_: Unavailable source, missing source

**Observation Order**:
The source-scoped order in which TowerGlance may compare observations when their Source Authority Rule proves a common ordering within the applicable Operational Session context. Receipt time alone creates no precedence, and observations from different sources or across a reconnect are not implicitly comparable.
_Avoid_: Arrival order, latest received wins

**Live Traffic Identity**:
The Operational Session-scoped source-correlation identity by which TowerGlance joins an observed Aircraft and its strip through the verified AIRPLANES and STRIPS relationship and, when proven, relates them to one Flight. It is not an independent Aircraft or Flight domain identity, and callsigns, source indices, and schedule rows do not carry identity across sessions.
_Avoid_: Callsign identity, persistent aircraft ID, Flight identity

**Flight Correlation**:
The evidence-backed determination that a planned Flight and a game-observed Flight describe the same movement. It requires one uniquely supported match with compatible direction, occurrence timing, origin, destination, and resolved Aircraft Type; a conflict preserves separate Flights, while game-object reuse begins a new occurrence and a new match.
_Avoid_: Global callsign match, nearest-time-only match, assumed merge

**Authoritative Absence**:
An explicit removal signal, or an explicitly empty fact or omission from an observation whose Source Authority Rule proves completeness for the affected category. A missing record in a partial update, delta, communication gap, or observation of unverified completeness is not proof of removal or lifecycle completion and may only leave current state unknown or stale or recovered.
_Avoid_: Not seen means removed, timeout deletion

**Capability Contract**:
The downstream definition of the smallest independently useful layer or action and its required and optional Normalized Facts. A supported unit is available only while every required Source Authority Rule is satisfied; optional gaps remain explicit, while unverified and unsupported units receive no operational availability status.
_Avoid_: Whole-application health, all-or-nothing capability

**Local Access**:
The default access boundary in which TowerGlance accepts browser clients only from the computer running TowerGlance.
_Avoid_: Offline mode
