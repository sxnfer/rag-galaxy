// An illustration, shown by the Journey only when there is no real trace to
// follow: nothing has been asked, and the server can't be reached for a saved
// example. The cars, cards and figures are the real ones from
// data/seeds/ev/vehicles.csv; the scores, timings and token counts are made
// up, and the page says so.
const card = (chunk_id, row, cls, make, drive, item, score, text, stats) => ({
  chunk_id, score, page_start: row, page_end: row, text,
  breadcrumb: `Electric cars › ${cls} › ${item} › Range`,
  meta: { item, class: cls, make, drive, facet: 'range', row, stats },
})
const SAMPLE_HITS = [
  card(441, 89, 'Large car', 'Lucid', 'AWD', 'Lucid Air G Touring XR AWD', 0.7712, 'Lucid Air G Touring XR AWD (large car) range: 512 miles on a full charge (very long), longest range of 231 cars and longest range among large cars. About 516 miles in the city and 507 on the highway.',
    { range_mi: 512, range_city_mi: 516, range_hwy_mi: 507, mpge: 128, kwh_per_100mi: 26.4, charge_240v_h: 13.0, annual_cost_usd: 600 }),
  card(196, 40, 'Pickup', 'Chevrolet', 'AWD', 'Chevrolet Silverado EV Max Range WT', 0.7493, 'Chevrolet Silverado EV Max Range WT (pickup truck) range: 493 miles on a full charge (very long), 2nd longest range of 231 cars and longest range among pickup trucks. About 539 miles in the city and 437 on the highway.',
    { range_mi: 493, range_city_mi: 539, range_hwy_mi: 437, mpge: 68, kwh_per_100mi: 49.5, charge_240v_h: 13.8, annual_cost_usd: 1100 }),
  card(466, 94, 'SUV', 'Lucid', 'AWD', 'Lucid Gravity GT', 0.7581, 'Lucid Gravity GT (SUV) range: 450 miles on a full charge (very long), 3rd longest range of 231 cars and longest range among SUVs. About 469 miles in the city and 426 on the highway.',
    { range_mi: 450, range_city_mi: 469, range_hwy_mi: 426, mpge: 108, kwh_per_100mi: 31.1, charge_240v_h: 9.5, annual_cost_usd: 700 }),
  card(456, 92, 'Large car', 'Lucid', 'AWD', 'Lucid Air Touring AWD', 0.7367, 'Lucid Air Touring AWD (large car) range: 431 miles on a full charge (very long), 4th longest range of 231 cars. About 437 miles in the city and 424 on the highway.',
    { range_mi: 431, range_city_mi: 437, range_hwy_mi: 424, mpge: 134, kwh_per_100mi: 25.2, charge_240v_h: 10.0, annual_cost_usd: 550 }),
  card(451, 91, 'Large car', 'Lucid', 'AWD', 'Lucid Air Sapphire AWD', 0.7402, 'Lucid Air Sapphire AWD (large car) range: 427 miles on a full charge (very long), 5th longest range of 231 cars. About 439 miles in the city and 412 on the highway.',
    { range_mi: 427, range_city_mi: 439, range_hwy_mi: 412, mpge: 105, kwh_per_100mi: 32.1, charge_240v_h: 13.0, annual_cost_usd: 700 }),
]
// 384 made-up numbers, scaled to length 1 like a real question.
const raw = Array.from({ length: 384 }, (_, i) => Math.sin(i * 12.9898) * Math.cos(i * 4.1414))
const norm = Math.hypot(...raw)

export const SAMPLE = {
  sample: true,
  trace_id: '00000000-0000-4000-8000-000000000000',
  question: 'which electric car has the longest range?',
  library: 'ev',
  stages: [
    { id: 'query', duration_ms: 18 }, { id: 'retrieve', duration_ms: 9 }, { id: 'rank', duration_ms: 1 },
    { id: 'assemble', duration_ms: 1 }, { id: 'generate', duration_ms: 1400 }, { id: 'check', duration_ms: 1 },
    { id: 'log', duration_ms: 4 },
  ],
  retrieval: {
    query_vector: raw.map((v) => Math.round((v / norm) * 10000) / 10000),
    query_position: [0.412, -0.236, 0.158],
    hits: SAMPLE_HITS,
  },
  rank: {
    understood: 'range · longest', applied: true, candidates: 50,
    stat: 'range', item_class: null, make: null, drive: null, direction: 'longest', column: 'range_mi',
    items: SAMPLE_HITS.map((h) => ({ item: h.meta.item, value: h.meta.stats.range_mi, unit: 'miles', chunk_id: h.chunk_id })),
    // What search alone put first: range cards, but not in range order.
    before: [
      { chunk_id: 441, item: 'Lucid Air G Touring XR AWD', facet: 'range', score: 0.7712 },
      { chunk_id: 466, item: 'Lucid Gravity GT', facet: 'range', score: 0.7581 },
      { chunk_id: 196, item: 'Chevrolet Silverado EV Max Range WT', facet: 'range', score: 0.7493 },
      { chunk_id: 446, item: 'Lucid Air Pure RWD', facet: 'range', score: 0.7455 },
      { chunk_id: 451, item: 'Lucid Air Sapphire AWD', facet: 'range', score: 0.7402 },
    ],
  },
  sources: SAMPLE_HITS.map((h, i) => ({
    label: `S${i + 1}`, chunk_id: h.chunk_id, breadcrumb: h.breadcrumb, pages: `row ${h.page_start}`, text: h.text, score: h.score,
  })),
  dropped: [],
  answer: '1. Lucid Air G Touring XR AWD: 512 miles [S1]\n2. Chevrolet Silverado EV Max Range WT: 493 miles [S2]\n3. Lucid Gravity GT: 450 miles [S3]\n4. Lucid Air Touring AWD: 431 miles [S4]\n5. Lucid Air Sapphire AWD: 427 miles [S5]',
  generation: { model: 'claude-haiku-5-5', input_tokens: 640, output_tokens: 92 },
  check: { passed: true, problems: [], cited: ['S1', 'S2', 'S3', 'S4', 'S5'] },
}
