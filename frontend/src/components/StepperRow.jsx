/**
 * Shared row used by both the bidding (GM) and trick-entry screens.
 *
 * A row displays a seat number + player name, plus either:
 *   - an inline stepper (when `isActive` is true), or
 *   - a confirmed value / status label (when inactive).
 *
 * Rows can optionally be tappable to request activation (used for re-editing
 * the most recently confirmed bid, and for selecting who to enter tricks for).
 */
export default function StepperRow({
  seatNumber,
  name,
  isDealer,
  subtitle,
  badge,
  isActive,
  stepperValue,
  onDecrement,
  onIncrement,
  decrementDisabled,
  incrementDisabled,
  confirmedValue,
  confirmedIcon,
  clickable,
  onClick,
}) {
  return (
    <div
      className={`brow ${isActive ? 'active' : ''}`}
      style={{
        cursor: clickable ? 'pointer' : 'default',
        background: isActive ? 'var(--accent-bg)' : undefined,
      }}
      onClick={clickable ? onClick : undefined}
    >
      <div
        className="seat"
        style={isActive ? { background: 'var(--amber)', color: '#fff' } : {}}
      >
        {seatNumber}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 14,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {name}
          {isDealer && <span style={{ fontSize: 10, color: 'var(--amber-text)' }}>🂠</span>}
        </div>
        {subtitle && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{subtitle}</div>
        )}
      </div>

      {badge}

      {isActive ? (
        <div className="stpr" onClick={(e) => e.stopPropagation()}>
          <button className="sbtn" onClick={onDecrement} disabled={decrementDisabled}>−</button>
          <span className="sval">{stepperValue}</span>
          <button className="sbtn" onClick={onIncrement} disabled={incrementDisabled}>+</button>
        </div>
      ) : confirmedValue !== undefined ? (
        <div className="bconf">{confirmedValue}</div>
      ) : confirmedIcon ? (
        <span style={{ fontSize: 16, color: 'var(--accent)', marginRight: 2 }}>{confirmedIcon}</span>
      ) : null}
    </div>
  )
}
