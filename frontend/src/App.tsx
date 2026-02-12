import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { DiscussionCreate } from './pages/DiscussionCreate'
import { DiscussionLive } from './pages/DiscussionLive'
import { SubmissionPage } from './pages/SubmissionPage'
import DiscussionReport from './pages/DiscussionReport'
import { SankeyView } from './pages/SankeyView'
import { DevUserSwitcher } from './components/DevUserSwitcher'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
// import './App.css' // Removed - using Tailwind CSS instead

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
          {/* Civic Header */}
          <header className="bg-white border-b border-slate-200 shadow-sm">
            <div className="container mx-auto px-4 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-xl">O</span>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-slate-900">OpenDiscuss</h1>
                    <p className="text-sm text-slate-600">Community Dialogue Platform</p>
                  </div>
                </div>
                <Badge variant="outline" className="text-indigo-600 border-indigo-200">Beta</Badge>
              </div>
            </div>
          </header>

          <main className="container mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/discussions/create" element={<DiscussionCreate />} />
              <Route path="/discussions/:discussionId/live" element={<DiscussionLive />} />
              <Route path="/discussions/:discussionId/submit" element={<SubmissionPage />} />
              <Route path="/discussions/:discussionId/report" element={<DiscussionReport />} />
              <Route path="/discussions/:discussionId/sankey" element={<SankeyView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          {/* Civic Footer */}
          <footer className="mt-16 bg-white border-t border-slate-200">
            <div className="container mx-auto px-4 py-6">
              <p className="text-center text-sm text-slate-600">
                OpenDiscuss • Facilitating structured community dialogue
              </p>
            </div>
          </footer>

          <DevUserSwitcher />
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

// Home page with navigation - Civic Design
function HomePage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Hero Section */}
      <Card className="border-2 border-indigo-100 bg-gradient-to-br from-white to-indigo-50/30">
        <CardHeader className="text-center pb-4">
          <CardTitle className="text-4xl font-bold text-slate-900 mb-3">
            Welcome to OpenDiscuss
          </CardTitle>
          <CardDescription className="text-lg text-slate-600">
            A structured discussion protocol for exploring diverse community perspectives
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center pb-8">
          <Button asChild size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-6 text-lg">
            <a href="/discussions/create">Create New Discussion</a>
          </Button>
        </CardContent>
      </Card>

      {/* Feature Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        <Card className="hover:shadow-lg transition-shadow border-l-4 border-l-blue-500">
          <CardHeader>
            <CardTitle className="text-lg text-blue-700">Structured Dialogue</CardTitle>
            <CardDescription>
              Round-based discussions that ensure everyone's voice is heard
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="hover:shadow-lg transition-shadow border-l-4 border-l-green-500">
          <CardHeader>
            <CardTitle className="text-lg text-green-700">Diverse Perspectives</CardTitle>
            <CardDescription>
              AI-powered clustering to identify and represent viewpoint diversity
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="hover:shadow-lg transition-shadow border-l-4 border-l-purple-500">
          <CardHeader>
            <CardTitle className="text-lg text-purple-700">Visual Analytics</CardTitle>
            <CardDescription>
              Sankey diagrams showing how perspectives evolve across rounds
            </CardDescription>
          </CardHeader>
        </Card>
      </div>

      {/* How It Works */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">How It Works</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-lg">1</div>
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-slate-900 mb-1">Create a Discussion</h4>
              <p className="text-slate-600 text-sm">Set up your topic, questions, and round structure</p>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-lg">2</div>
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-slate-900 mb-1">Participants Respond</h4>
              <p className="text-slate-600 text-sm">Each person shares their perspective in structured rounds</p>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-lg">3</div>
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-slate-900 mb-1">AI Analyzes & Clusters</h4>
              <p className="text-slate-600 text-sm">Perspectives are grouped to identify common themes and outliers</p>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-lg">4</div>
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-slate-900 mb-1">Visualize Results</h4>
              <p className="text-slate-600 text-sm">View how perspectives evolved with interactive Sankey diagrams</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Benefits */}
      <Card className="bg-gradient-to-br from-indigo-50 to-white">
        <CardHeader>
          <CardTitle className="text-xl text-center">Why OpenDiscuss?</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div className="flex items-start gap-2">
              <Badge variant="default" className="mt-0.5">✓</Badge>
              <span className="text-slate-700">Ensures all voices are heard equally</span>
            </div>
            <div className="flex items-start gap-2">
              <Badge variant="default" className="mt-0.5">✓</Badge>
              <span className="text-slate-700">Identifies consensus and divergence</span>
            </div>
            <div className="flex items-start gap-2">
              <Badge variant="default" className="mt-0.5">✓</Badge>
              <span className="text-slate-700">Transparent AI-powered analysis</span>
            </div>
            <div className="flex items-start gap-2">
              <Badge variant="default" className="mt-0.5">✓</Badge>
              <span className="text-slate-700">Visual tracking of opinion evolution</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
