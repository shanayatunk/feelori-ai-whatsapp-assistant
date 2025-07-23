import { useState, useEffect } from 'react'
import { 
  MessageSquare, 
  Users, 
  ShoppingCart, 
  TrendingUp, 
  Clock,
  CheckCircle,
  AlertCircle,
  Bot
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'

const conversationData = [
  { name: 'Mon', conversations: 45, resolved: 42 },
  { name: 'Tue', conversations: 52, resolved: 48 },
  { name: 'Wed', conversations: 38, resolved: 36 },
  { name: 'Thu', conversations: 61, resolved: 58 },
  { name: 'Fri', conversations: 73, resolved: 69 },
  { name: 'Sat', conversations: 29, resolved: 27 },
  { name: 'Sun', conversations: 34, resolved: 32 },
]

const intentData = [
  { name: 'Product Query', value: 35, color: '#8884d8' },
  { name: 'Order Status', value: 28, color: '#82ca9d' },
  { name: 'Policy Question', value: 20, color: '#ffc658' },
  { name: 'General', value: 12, color: '#ff7300' },
  { name: 'Escalation', value: 5, color: '#ff0000' },
]

const responseTimeData = [
  { hour: '00', avgTime: 2.3 },
  { hour: '04', avgTime: 1.8 },
  { hour: '08', avgTime: 3.2 },
  { hour: '12', avgTime: 4.1 },
  { hour: '16', avgTime: 3.8 },
  { hour: '20', avgTime: 2.9 },
]

export function Dashboard() {
  const [metrics, setMetrics] = useState({
    totalConversations: 0,
    activeUsers: 0,
    totalOrders: 0,
    avgResponseTime: 0,
    resolutionRate: 0,
    customerSatisfaction: 0
  })

  const [recentActivity, setRecentActivity] = useState([])

  useEffect(() => {
    // Simulate loading metrics
    const timer = setTimeout(() => {
      setMetrics({
        totalConversations: 1247,
        activeUsers: 89,
        totalOrders: 342,
        avgResponseTime: 2.8,
        resolutionRate: 94.2,
        customerSatisfaction: 4.6
      })

      setRecentActivity([
        {
          id: 1,
          type: 'conversation',
          message: 'New conversation started with customer about order #1234',
          time: '2 minutes ago',
          status: 'active'
        },
        {
          id: 2,
          type: 'order',
          message: 'Order #1235 processed automatically',
          time: '5 minutes ago',
          status: 'completed'
        },
        {
          id: 3,
          type: 'escalation',
          message: 'Conversation escalated to human agent',
          time: '8 minutes ago',
          status: 'escalated'
        },
        {
          id: 4,
          type: 'knowledge',
          message: 'New FAQ added to knowledge base',
          time: '15 minutes ago',
          status: 'completed'
        }
      ])
    }, 1000)

    return () => clearTimeout(timer)
  }, [])

  const getActivityIcon = (type) => {
    switch (type) {
      case 'conversation':
        return <MessageSquare className="h-4 w-4" />
      case 'order':
        return <ShoppingCart className="h-4 w-4" />
      case 'escalation':
        return <AlertCircle className="h-4 w-4" />
      case 'knowledge':
        return <Bot className="h-4 w-4" />
      default:
        return <CheckCircle className="h-4 w-4" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active':
        return 'bg-blue-500'
      case 'completed':
        return 'bg-green-500'
      case 'escalated':
        return 'bg-orange-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your AI assistant performance and metrics
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Conversations</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.totalConversations.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600">+12%</span> from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.activeUsers}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600">+5%</span> from yesterday
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Orders Processed</CardTitle>
            <ShoppingCart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.totalOrders}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600">+8%</span> from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.avgResponseTime}s</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600">-0.3s</span> from last week
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Resolution Rate</CardTitle>
            <CardDescription>Percentage of conversations resolved automatically</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-3xl font-bold">{metrics.resolutionRate}%</div>
            <Progress value={metrics.resolutionRate} className="w-full" />
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Target: 90%</span>
              <span className="text-green-600">Above target</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Customer Satisfaction</CardTitle>
            <CardDescription>Average rating from customer feedback</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-3xl font-bold">{metrics.customerSatisfaction}/5.0</div>
            <Progress value={(metrics.customerSatisfaction / 5) * 100} className="w-full" />
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Target: 4.5</span>
              <span className="text-green-600">Above target</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Conversation Trends */}
        <Card>
          <CardHeader>
            <CardTitle>Conversation Trends</CardTitle>
            <CardDescription>Daily conversation volume and resolution rate</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={conversationData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="conversations" 
                  stroke="#8884d8" 
                  strokeWidth={2}
                  name="Total Conversations"
                />
                <Line 
                  type="monotone" 
                  dataKey="resolved" 
                  stroke="#82ca9d" 
                  strokeWidth={2}
                  name="Resolved"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Intent Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Intent Distribution</CardTitle>
            <CardDescription>Breakdown of conversation intents</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={intentData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {intentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Response Time Trends */}
        <Card>
          <CardHeader>
            <CardTitle>Response Time by Hour</CardTitle>
            <CardDescription>Average response time throughout the day</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={responseTimeData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis />
                <Tooltip />
                <Area 
                  type="monotone" 
                  dataKey="avgTime" 
                  stroke="#8884d8" 
                  fill="#8884d8" 
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest system events and updates</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start space-x-3">
                  <div className={`p-1 rounded-full ${getStatusColor(activity.status)}`}>
                    <div className="text-white">
                      {getActivityIcon(activity.type)}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">
                      {activity.message}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {activity.time}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {activity.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

