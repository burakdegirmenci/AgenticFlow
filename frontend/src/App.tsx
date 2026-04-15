import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "@/components/common/Layout";
import Dashboard from "@/pages/Dashboard";
import ExecutionDetail from "@/pages/ExecutionDetail";
import ExecutionHistory from "@/pages/ExecutionHistory";
import Settings from "@/pages/Settings";
import Sites from "@/pages/Sites";
import SupportAgent from "@/pages/SupportAgent";
import WorkflowEditor from "@/pages/WorkflowEditor";
import WorkflowList from "@/pages/WorkflowList";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/sites" element={<Sites />} />
        <Route path="/workflows" element={<WorkflowList />} />
        <Route path="/workflows/:id" element={<WorkflowEditor />} />
        <Route path="/executions" element={<ExecutionHistory />} />
        <Route path="/executions/:id" element={<ExecutionDetail />} />
        <Route path="/support" element={<SupportAgent />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
