import {
  ArrowDownOutlined, ArrowUpOutlined, BankOutlined, CarOutlined, CheckCircleFilled, ClockCircleOutlined, DatabaseOutlined,
  DollarOutlined, MinusOutlined, TeamOutlined, WalletOutlined,
} from '@ant-design/icons'
import { Alert, Button, Card, Col, Empty, Row, Skeleton, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import type { Dashboard } from '@/api/types'
import { DateField } from '@/components/DateField'
import { HeroBanner } from '@/components/HeroBanner'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, rangeFromUrl, today } from '@/lib/date'
import { formatCurrency, formatQty, formatShort, toNumber } from '@/lib/format'
import { SalesChart } from './SalesChart'

const GOOD = '#2f7d4f'
const BAD = '#b23a48'
const WARN = '#b45309'
const INK = '#17283a'
const cardStyle = { borderRadius: 12, borderColor: '#edf0f3', boxShadow: '0 1px 3px rgba(16,38,59,.06)', height: '100%' }

const rs = (v: string | number) => formatCurrency(v).replace(/\.00$/, '')

/** Section heading phrased as the question it answers, so the owner knows what to look at. */
function Section({ title, hint, extra, children }: { title: string; hint: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <section className="dash-section">
      <div className="dash-section-head">
        <Typography.Title level={5} style={{ margin: 0 }}>{title}</Typography.Title>
        <Typography.Text type="secondary">{hint}</Typography.Text>
        {extra && <div className="dash-section-extra">{extra}</div>}
      </div>
      {children}
    </section>
  )
}

/** "vs yesterday" line: arrow icon carries direction (green when up is good), the words carry the meaning. */
function Change({ now, before, label, upIsGood = true, money = true }: { now: number; before: number; label: string; upIsGood?: boolean; money?: boolean }) {
  const diff = now - before
  const fmt = (v: number) => (money ? rs(v) : String(v))
  if (diff === 0) return <span className="dash-change"><MinusOutlined /> Same as {label} ({fmt(before)})</span>
  const up = diff > 0
  const good = up === upIsGood
  return (
    <span className="dash-change">
      <span style={{ color: good ? GOOD : BAD }}>{up ? <ArrowUpOutlined /> : <ArrowDownOutlined />}</span>{' '}
      {money ? `${formatShort(Math.abs(diff))} ${up ? 'more' : 'less'}` : `${Math.abs(diff)} ${up ? 'more' : 'fewer'}`} than {label} ({fmt(before)})
    </span>
  )
}

function TodayTile({ label, value, icon, foot, to }: { label: string; value: ReactNode; icon: ReactNode; foot: ReactNode; to?: string }) {
  const body = (
    <Card size="small" hoverable={Boolean(to)} style={cardStyle} styles={{ body: { padding: 16 } }}>
      <div className="dash-tile-label">{icon}{label}{to && <span className="dash-tile-open" aria-hidden><span className="dash-open-word">Open </span>›</span>}</div>
      <div className="dash-tile-value">{value}</div>
      <div className="dash-tile-foot">{foot}</div>
    </Card>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

/** Horizontal bars for one series (who owes most, yard stock value); value sits at the bar's end. */
function BarList({ rows, empty }: { rows: { key: string | number; label: ReactNode; value: number; text: string; warn?: boolean }[]; empty: string }) {
  if (!rows.length) return <Typography.Text type="secondary">{empty}</Typography.Text>
  const max = Math.max(...rows.map((r) => r.value), 1)
  return (
    <div className="bar-list">
      {rows.map((r) => (
        <div key={r.key} className="bar-row">
          <div className="bar-label">{r.label}</div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${Math.max((r.value / max) * 100, r.value > 0 ? 2 : 0)}%` }} />
          </div>
          <span className="bar-value" style={{ color: r.warn ? WARN : undefined }}>{r.text}</span>
        </div>
      ))}
    </div>
  )
}

interface Todo { key: string; tone: 'bad' | 'warn'; icon: ReactNode; text: ReactNode; action?: { to: string; label: string } }

export default function DashboardPage() {
  // The day being looked at lives in the link (?date=), so Back from a drill-down returns to the same day.
  const [search, setSearch] = useSearchParams()
  const day = rangeFromUrl(search)?.[0] ?? today()
  const isToday = day === today()
  const setDay = (iso: string) => setSearch(iso === today() ? {} : { date: iso }, { replace: true })
  const { data: d, isLoading, error } = useGet<Dashboard>('/reports/dashboard', { on: day }, { staleTime: 10_000 })
  const canKhata = usePermission('report.khata')
  const canMoneyLines = usePermission('report.cashbook')
  if (error) return <Alert type="error" showIcon message={apiError(error).message} />
  if (isLoading || !d) return <><HeroBanner /><Skeleton active paragraph={{ rows: 10 }} /></>
  const dayWord = isToday ? 'today' : `on ${formatDate(day)}`
  const before = isToday ? 'yesterday' : 'the day before'
  const moneyLink = (direction: 'in' | 'out') => (canMoneyLines ? `/reports/money-moves?date=${day}&direction=${direction}` : `/payments?date=${day}`)

  const n = toNumber
  const inHand = n(d.cash_in_hand) + n(d.bank_balance)
  const weOwe = n(d.total_payable) + n(d.staff_payable)
  const afterSettling = inHand + n(d.total_receivable) - weOwe
  const monthChange = n(d.sales_prev_month) > 0 ? ((n(d.sales_month) - n(d.sales_prev_month)) / n(d.sales_prev_month)) * 100 : null
  const working = d.vehicles.filter((v) => v.trips > 0).length
  const finished = d.stock.filter((s) => n(s.qty) <= 0)
  const khata = (id: number) => (canKhata ? { to: `/reports/khata?party=${id}`, label: 'Open khata' } : undefined)

  const todos: Todo[] = [
    ...d.old_udhaar.slice(0, 4).map((u) => ({
      key: `u${u.party_id}`, tone: u.days > 30 ? 'bad' as const : 'warn' as const, icon: <ClockCircleOutlined />,
      text: <><strong>{u.name}</strong> owes {rs(u.balance)}, unpaid for <strong>{u.days} days</strong></>, action: khata(u.party_id),
    })),
    ...d.advance_low.slice(0, 3).map((a) => ({
      key: `a${a.party_id}`, tone: 'warn' as const, icon: <WalletOutlined />,
      text: <><strong>{a.name}</strong>: advance almost used up, only {rs(a.advance)} left. Ask for more before the next trip.</>, action: khata(a.party_id),
    })),
    ...finished.map((s) => ({
      key: `s${s.material}`, tone: 'bad' as const, icon: <DatabaseOutlined />,
      text: <><strong>{s.material}</strong> is finished in the yard{n(s.qty) < 0 ? ` (short by ${formatQty(-n(s.qty))} ${s.unit})` : ''}. Enter the next purchase.</>,
      action: { to: '/purchases', label: 'Purchases' },
    })),
    ...(n(d.staff_payable) > 0
      ? [{ key: 'wages', tone: 'warn' as const, icon: <TeamOutlined />, text: <>Wages due to staff: <strong>{rs(d.staff_payable)}</strong></>, action: { to: '/labour', label: 'Labour & wages' } }]
      : []),
  ]

  return (
    <div className="dash">
      <HeroBanner date={d.date} trips={d.trips_today} isToday={isToday} />

      <Section
        title={isToday ? 'Today' : formatDate(day)}
        hint={`What happened ${dayWord}, compared with ${before}. Tap a box to see the entries.`}
        extra={
          <div className="dash-day-pick">
            <div style={{ width: 150 }}><DateField id="dash-day" value={day} onChange={setDay} /></div>
            {!isToday && <Button onClick={() => setDay(today())}>Today</Button>}
          </div>
        }
      >
        <Row gutter={[12, 12]}>
          <Col xs={12} lg={6}>
            <TodayTile label="Trips" icon={<CarOutlined />} value={d.trips_today} to={`/challans?date=${day}`}
              foot={<Change now={d.trips_today} before={d.trips_yesterday} label={before} money={false} />} />
          </Col>
          <Col xs={12} lg={6}>
            <TodayTile label="Sales" icon={<DollarOutlined />} value={rs(d.sales_today)} to={`/challans?date=${day}`}
              foot={<Change now={n(d.sales_today)} before={n(d.sales_yesterday)} label={before} />} />
          </Col>
          <Col xs={12} lg={6}>
            <TodayTile label="Money received" icon={<ArrowDownOutlined style={{ color: GOOD }} />} value={rs(d.money_in_today)} to={moneyLink('in')}
              foot={<span className="dash-change">Came into cash and bank {dayWord}</span>} />
          </Col>
          <Col xs={12} lg={6}>
            <TodayTile label="Money paid out" icon={<ArrowUpOutlined style={{ color: BAD }} />} value={rs(d.money_out_today)} to={moneyLink('out')}
              foot={<span className="dash-change">Went out of cash and bank {dayWord}</span>} />
          </Col>
        </Row>
      </Section>

      <Section title="Needs attention" hint="Things to follow up on, most urgent first">
        <Card size="small" style={cardStyle} styles={{ body: { padding: todos.length ? 6 : 16 } }}>
          {todos.length === 0 ? (
            <div className="todo-clear"><CheckCircleFilled style={{ color: GOOD }} /> All clear. No old udhaar, no finished stock, no wages due.</div>
          ) : (
            todos.map((t) => (
              <div key={t.key} className="todo-row">
                <span className={`todo-icon todo-${t.tone}`}>{t.icon}</span>
                <span className="todo-text">{t.text}</span>
                {t.action && <Link className="todo-action" to={t.action.to}>{t.action.label}</Link>}
              </div>
            ))
          )}
        </Card>
      </Section>

      <Section title="Where is the money" hint="Cash in hand, what customers owe you, and what you owe">
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={8}>
            <Card size="small" style={cardStyle} title={<><WalletOutlined /> In hand</>}>
              <div className="dash-big">{rs(inHand)}</div>
              <div className="kv"><span><WalletOutlined /> Cash</span><strong>{rs(d.cash_in_hand)}</strong></div>
              <div className="kv"><span><BankOutlined /> Bank / wallet</span><strong>{rs(d.bank_balance)}</strong></div>
              <div className="dash-settle">
                <Typography.Text type="secondary">If everyone pays you and you pay everyone, you are left with</Typography.Text>
                <div className="dash-settle-value" style={{ color: afterSettling < 0 ? BAD : INK }}>{rs(afterSettling)}</div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>Plus yard stock worth {rs(d.stock_value)}</Typography.Text>
              </div>
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Card size="small" style={cardStyle} title="Customers owe you (udhaar)">
              <div className="dash-big">{rs(d.total_receivable)}</div>
              <Typography.Text type="secondary" className="dash-sub">Biggest balances</Typography.Text>
              <BarList empty="Nobody owes you anything" rows={d.top_debtors.map((r) => ({
                key: r.party_id, value: n(r.balance), text: formatShort(r.balance),
                label: canKhata ? <Link to={`/reports/khata?party=${r.party_id}`}>{r.name}</Link> : r.name,
              }))} />
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Card size="small" style={cardStyle} title="You owe">
              <div className="dash-big">{rs(weOwe)}</div>
              <div className="kv"><span>Suppliers</span><strong>{rs(d.total_payable)}</strong></div>
              <div className="kv"><span>Staff wages</span><strong>{rs(d.staff_payable)}</strong></div>
              <Typography.Text type="secondary" className="dash-sub">Biggest supplier balances</Typography.Text>
              <BarList empty="You owe no supplier" rows={d.top_owed.map((r) => ({
                key: r.party_id, value: n(r.balance), text: formatShort(r.balance),
                label: canKhata ? <Link to={`/reports/khata?party=${r.party_id}`}>{r.name}</Link> : r.name,
              }))} />
            </Card>
          </Col>
        </Row>
      </Section>

      <Section title="How business is going" hint="Sales over the last two weeks and this month against last month">
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={d.profit_month ? 16 : 24}>
            <Card size="small" style={cardStyle} title="Sales, last 14 days">
              <div className="month-line">
                <span>This month so far <strong>{rs(d.sales_month)}</strong></span>
                {monthChange !== null && (
                  <span className="dash-change">
                    <span style={{ color: monthChange >= 0 ? GOOD : BAD }}>{monthChange >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}</span>{' '}
                    {Math.abs(monthChange).toFixed(0)}% {monthChange >= 0 ? 'more' : 'less'} than the same days last month ({formatShort(d.sales_prev_month)})
                  </span>
                )}
              </div>
              <SalesChart days={d.daily} />
            </Card>
          </Col>
          {d.profit_month && (
            <Col xs={24} lg={8}>
              <Card size="small" style={cardStyle} title="Profit this month">
                <div className="dash-big" style={{ color: n(d.profit_month.profit) < 0 ? BAD : INK }}>{rs(d.profit_month.profit)}</div>
                <Typography.Text type="secondary">{n(d.profit_month.profit) >= 0 ? 'Earned after all costs' : 'Loss after all costs'}</Typography.Text>
                <div className="kv" style={{ marginTop: 12 }}><span>Income (sales, freight, rent)</span><strong>{rs(d.profit_month.income)}</strong></div>
                <div className="kv"><span>Costs (material, diesel, wages...)</span><strong>{rs(d.profit_month.expense)}</strong></div>
                {n(d.profit_month.income) > 0 && (
                  <div className="margin-meter" aria-label="Profit share of income">
                    <div className="margin-track"><div className="margin-fill" style={{ width: `${Math.min(Math.max((n(d.profit_month.profit) / n(d.profit_month.income)) * 100, 0), 100)}%` }} /></div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      You keep about <strong>Rs {Math.max(Math.round((n(d.profit_month.profit) / n(d.profit_month.income)) * 100), 0)}</strong> of every Rs 100 earned
                    </Typography.Text>
                  </div>
                )}
                <Link to="/reports/profit-loss" style={{ display: 'inline-block', marginTop: 10 }}>Full profit & loss</Link>
              </Card>
            </Col>
          )}
        </Row>
      </Section>

      <Section title="Vehicles and yard" hint={`Which vehicles worked ${dayWord} and what material is in the yard now`}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <Card size="small" style={cardStyle} title={`${working} of ${d.vehicles.length} vehicles working ${dayWord}`}>
              {d.vehicles.length === 0 ? <Empty description="No vehicles yet" /> : (
                <div className="fleet">
                  {d.vehicles.map((v) => (
                    <div key={v.id} className={`fleet-chip ${v.trips ? 'on' : 'off'}`}>
                      <CarOutlined />
                      <div>
                        <div className="fleet-name">{v.name}</div>
                        <div className="fleet-trips">{v.trips ? `${v.trips} trip${v.trips === 1 ? '' : 's'}` : 'Idle'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {d.trips_by_material.length > 0 && (
                <Typography.Paragraph type="secondary" style={{ margin: '12px 0 0' }}>
                  Sent out {dayWord}: {d.trips_by_material.map((m) => `${m.material} ${formatQty(m.qty)} ${m.unit}`).join(' · ')}
                </Typography.Paragraph>
              )}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card size="small" style={cardStyle} title={<>Yard stock <Typography.Text type="secondary" style={{ fontWeight: 400 }}>worth {rs(d.stock_value)}</Typography.Text></>}
              extra={<Link to="/stock">Open</Link>}>
              <BarList empty="No materials yet" rows={d.stock.map((s) => ({
                key: s.material, value: Math.max(n(s.value), 0), warn: n(s.qty) <= 0,
                label: s.material,
                text: n(s.qty) <= 0 ? `Finished${n(s.qty) < 0 ? ` (${formatQty(s.qty)} ${s.unit})` : ''}` : `${formatQty(s.qty)} ${s.unit} · ${formatShort(s.value)}`,
              }))} />
            </Card>
          </Col>
        </Row>
      </Section>
    </div>
  )
}
