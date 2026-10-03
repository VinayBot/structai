import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ChatPage } from './pages/ChatPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ArchitecturePage } from './pages/ArchitecturePage'
import { TracesPage } from './pages/TracesPage'
import { MetricsPage } from './pages/MetricsPage'
import { EvaluationPage } from './pages/EvaluationPage'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route path="/app" element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="chat" replace />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            <Route path="traces" element={<TracesPage />} />
            <Route path="metrics" element={<MetricsPage />} />
            <Route path="evaluation" element={<EvaluationPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
