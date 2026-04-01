import { configureApiClient } from "./api/client";
import { AssessPage } from "./pages/AssessPage";

configureApiClient({
  baseUrl: "",
  apiKey: import.meta.env.VITE_API_KEY ?? "",
});

export function App() {
  return <AssessPage />;
}
