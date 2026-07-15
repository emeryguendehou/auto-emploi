import type { QuotasData } from '../api/api';

interface Props {
  data: QuotasData | null;
}

export default function QuotaTable({ data }: Props) {
  if (!data) return null;
  const { quotas, today_usage } = data;

  return (
    <table className="quota-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>Model</th>
          <th>Daily Limit</th>
          <th>TPM Limit</th>
          <th>Delay</th>
          <th>Used Today</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(quotas).map(([name, q]) => {
          const usage = today_usage[name];
          const used = usage?.used ?? 0;
          const pct = q.daily_limit ? Math.min(100, Math.round((used / q.daily_limit) * 100)) : 0;
          return (
            <tr key={name}>
              <td><strong>{name}</strong></td>
              <td className="td-model">{q.model}</td>
              <td>{q.daily_limit}</td>
              <td>{q.tpm_limit ?? '—'}</td>
              <td>{q.delay_seconds}s</td>
              <td>
                <div className="quota-bar-track">
                  <div
                    className="quota-bar-fill"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="quota-num">{used}/{q.daily_limit}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
