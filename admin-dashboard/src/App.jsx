import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Header } from './components/Header'
import { Dashboard } from './components/Dashboard'
import { Conversations } from './components/Conversations'
import { Analytics } from './components/Analytics'
import { KnowledgeBase } from './components/KnowledgeBase'
import { Settings } from './components/Settings'
import { Orders } from './components/Orders'
import { Products } from './components/Products'
import './App.css'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [darkMode, setDarkMode] = useState(false)

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen)
  const toggleDarkMode = () => {
    setDarkMode(!darkMode)
    document.documentElement.classList.toggle('dark')
  }

  return (
    <Router>
      <div className={`min-h-screen bg-background ${darkMode ? 'dark' : ''}`}>
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          
          {/* Main Content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Header */}
            <Header 
              onMenuClick={toggleSidebar}
              onDarkModeToggle={toggleDarkMode}
              darkMode={darkMode}
            />
            
            {/* Main Content Area */}
            <main className="flex-1 overflow-x-hidden overflow-y-auto bg-background p-6">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/conversations" element={<Conversations />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/knowledge" element={<KnowledgeBase />} />
                <Route path="/orders" element={<Orders />} />
                <Route path="/products" element={<Products />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </main>
          </div>
        </div>
      </div>
    </Router>
  )
}

export default App

