# Class profile

## Semantic contract
Show only relevant classes/interfaces/enums. Distinguish inheritance, realization,
composition, aggregation, association and dependency. Arrowhead must point to the
correct parent/target. Members are curated for the story. Hide generated/framework
types unless material. Package groups must be real.

## Presentation contract
Inheritance reads top-down. Interfaces stay near implementations. Dependency lines are
secondary to inheritance/composition. Keep boxes comparable in density. ≤12 classes by
default. Use stereotypes consistently rather than decorative colour.

## Renderer
PlantUML preferred; Mermaid classDiagram fallback.

## Blocking
Wrong relation type; composition/aggregation guessed; exhaustive member dumps; false
package boundary; generated/util types drowning the model.
