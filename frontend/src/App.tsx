import { configureApiClient } from "./api/client";
import { AssessPage } from "./pages/AssessPage";

configureApiClient({
  baseUrl: "/web/api",
});

export function App() {
  return <AssessPage />;
}
