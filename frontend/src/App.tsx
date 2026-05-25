import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { OAuthCallbackPage } from "./pages/OAuthCallbackPage";
import { SignupPage } from "./pages/SignupPage";
import { MyPage } from "./pages/MyPage";
import { PlayPage } from "./pages/PlayPage";
import { PlaySetupPage } from "./pages/PlaySetupPage";
import { WorldBrowsePage } from "./pages/WorldBrowsePage";
import { WorldEditorPage } from "./pages/WorldEditorPage";
import { InstallToast } from "./pwa/InstallToast";

function WorldEditorNewRoute() {
  return <WorldEditorPage key="world-route-new" create />;
}

function WorldEditorEditRoute() {
  const { worldId } = useParams<{ worldId: string }>();
  return <WorldEditorPage key={`world-route-${worldId ?? ""}`} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <InstallToast />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
        <Route path="/explore" element={<Navigate to="/" replace />} />
        <Route path="/my" element={<MyPage />} />
        <Route path="/worlds" element={<Navigate to="/my" replace />} />
        <Route path="/play" element={<Navigate to="/my" replace />} />
        <Route path="/world/:worldId" element={<WorldBrowsePage />} />
        <Route path="/worlds/new" element={<WorldEditorNewRoute />} />
        <Route path="/worlds/:worldId" element={<WorldEditorEditRoute />} />
        <Route path="/play/setup/:worldId" element={<PlaySetupPage />} />
        <Route path="/play/:sessionId" element={<PlayPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
