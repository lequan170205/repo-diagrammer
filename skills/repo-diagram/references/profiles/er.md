# ER profile

Evidence priority: live constraints → migrations → schema definition → ORM model.

## Semantic contract
Declare **physical** or **logical** mode. Physical views show real tables/entities,
PK/FK/UK and cardinality from constraints. Logical views do not invent relational
foreign keys. Nullable FK changes minimum cardinality; unique FK can change
one-to-many to one-to-one. Join tables remain visible in physical views.

## Presentation contract
Cardinality readable at 100%. Show only identity/relationship/business attributes
unless a full physical schema was requested. Group by real schema/bounded context.
≤15 entities per view.

## Renderer
Mermaid erDiagram preferred; PlantUML fallback.

## Blocking
Guessed cardinality; reversed FK; nullable/unique constraint ignored; logical/physical
mixed silently; high-level ERD filled with every column.
