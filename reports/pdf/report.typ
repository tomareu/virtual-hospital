// --- Data ---

#let data = json(bytes(sys.inputs.data))

// --- Palette ---

#let ink = rgb("#4a6572")
#let deep = rgb("#6fa8c0")
#let soft = rgb("#a8d8e8")
#let sky = rgb("#cfe8f3")
#let mist = rgb("#eef6fa")
#let cream = rgb("#fdf9f3")

#let radius = 14pt
#let dashed(paint) = (paint: paint, thickness: 1.2pt, dash: "dashed")

// --- Document ---

#set document(title: data.document_title, author: "My Little Virtual Hospital")
#set text(font: ("Noto Sans", "Noto Emoji"), size: 10.5pt, fill: ink, lang: data.language)
#set par(leading: 0.65em, spacing: 0.9em)
#set page(
  paper: "a4",
  margin: (x: 18mm, top: 16mm, bottom: 24mm),
  footer: context {
    set text(size: 8pt)
    line(length: 100%, stroke: dashed(soft))
    grid(
      columns: (1fr, auto),
      column-gutter: 16pt,
      data.footer,
      counter(page).display("1 / 1", both: true),
    )
  },
)

#show heading.where(level: 1): set text(size: 19pt, weight: 800)
#show heading.where(level: 2): set text(size: 12pt, weight: 800)
#show heading: set block(above: 0pt, below: 10pt)
#show regex("\S{24}"): it => it + sym.zws

#let caption(body) = text(size: 7.5pt, weight: 800, tracking: 0.06em, upper(body))

#let card(fill: none, stroke: none, body) = block(
  width: 100%,
  fill: fill,
  stroke: stroke,
  radius: radius,
  inset: 14pt,
  body,
)

// --- Header ---

#grid(
  columns: (auto, 1fr),
  align: (horizon, right + horizon),
  image("/brand/mlvh.svg", height: 18mm, alt: "My Little Virtual Hospital"),
  [
    #heading(level: 1, data.heading)
    #set text(size: 9pt)
    #data.reference \
    #data.issued
  ],
)

#v(12pt)

// --- Patient ---

#card(fill: mist)[
  #grid(
    columns: (30mm, 1fr),
    column-gutter: 16pt,
    align: horizon,
    box(
      width: 30mm,
      height: 30mm,
      fill: sky,
      radius: radius,
      clip: true,
      image(data.patient.avatar, width: 100%, height: 100%, fit: "cover", alt: data.patient.avatar_alt),
    ),
    [
      #heading(level: 2)[#text(size: 16pt, data.patient.name) #h(4pt) #text(size: 9pt, weight: 600)[[#data.patient.code]]]
      #grid(
        columns: (auto, 1fr, auto, 1fr),
        column-gutter: (8pt, 16pt, 8pt),
        row-gutter: 8pt,
        align: (left + horizon,) * 4,
        ..data.patient.rows.map(((label, value)) => (caption(label), value)).flatten(),
      )
    ],
  )
]

#v(10pt)

// --- Visit ---

#grid(
  columns: (1fr,) * data.visit.len(),
  column-gutter: 10pt,
  ..data.visit.map(((label, value)) => block(
    width: 100%,
    stroke: dashed(soft),
    radius: radius,
    inset: (x: 12pt, y: 9pt),
    stack(spacing: 5pt, caption(label), text(weight: 700, value)),
  )),
)

#v(10pt)

// --- Summary ---

#card(fill: cream, stroke: dashed(deep))[
  #heading(level: 2, data.summary.heading)
  #data.summary.text
]

#v(10pt)

// --- Record details ---

#card(stroke: dashed(soft))[
  #heading(level: 2, data.details.heading)
  #for (label, value) in data.details.rows [
    #block(above: 12pt, below: 0pt)[
      #caption(label)
      #v(2pt)
      #value
    ]
  ]
]

// --- Indications ---

#if data.indications != none [
  #v(10pt)
  #card(fill: sky)[
    #heading(level: 2, data.indications.heading)
    #text(size: 11.5pt, data.indications.text)
  ]
]
