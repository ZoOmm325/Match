import HistoryItem, { type HistoryRecord } from "@/components/HistoryItem";
import EmptyState from "@/components/ui/EmptyState";
import Loading from "@/components/ui/Loading";

interface HistoryListProps {
  records: HistoryRecord[];
  loading: boolean;
}

export default function HistoryList({ records, loading }: HistoryListProps) {
  if (loading) {
    return <Loading label="正在加载历史记录" />;
  }

  if (!records.length) {
    return <EmptyState title="暂无历史记录" description="完成一次岗位匹配后，记录会显示在这里。" />;
  }

  return (
    <div className="space-y-4">
      {records.map((record) => (
        <HistoryItem key={record.id} record={record} />
      ))}
    </div>
  );
}
