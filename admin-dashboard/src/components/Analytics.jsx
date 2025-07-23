import { useState, useEffect } from 'react'
import { 
  TrendingUp, 
  TrendingDown, 
  Users, 
  MessageSquare, 
  Clock, 
  Target,
  Download,
  Calendar
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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

const performanceData = [
  { date: '2024-01-01', conversations: 45, resolved: 42, escalated: 3, avgResponseTime: 2.3 },
  { date: '2024-01-02', conversations: 52, resolved: 48, escalated: 4, avgResponseTime: 2.1 },
  { date: '2024-01-03', conversations: 38, resolved: 36, escalated: 2, avgResponseTime: 2.5 },
  { date: '2024-01-04', conversations: 61, resolved: 58, escalated: 3, avgResponseTime: 2.0 },
  { date: '2024-01-05', conversations: 73, resolved: 69, escalated: 4, avgResponseTime: 1.9 },
  { date: '2024-01-06', conversations: 29, resolved: 27, escalated: 2, avgResponseTime: 2.2 },
  { date: '2024-01-07', conversations: 34, resolved: 32, escalated: 2, avgResponseTime: 2.4 },
]

const intentAnalytics = [
  { intent: 'Product Query', count: 156, percentage: 35, trend: 'up' },
  { intent: 'Order Status', count: 124, percentage: 28, trend: 'up' },
  { intent: 'Policy Question', count: 89, percentage: 20, trend: 'down' },
  { intent: 'General Support', count: 53, percentage: 12, trend: 'stable' },
  { intent: 'Escalation', count: 22, percentage: 5, trend: 'down' },
]

const customerSatisfactionData = [
  { rating: '5 Stars', count: 145, percentage: 65 },
  { rating: '4 Stars', count: 45, percentage: 20 },
  { rating: '3 Stars', count: 22, percentage: 10 },
  { rating: '2 Stars', count: 7, percentage: 3 },
  { rating: '1 Star', count: 4, percentage: 2 },
]

const hourlyData = [
  { hour: '00:00', conversations: 5, avgResponseTime: 1.8 },
  { hour: '02:00', conversations: 3, avgResponseTime: 1.5 },
  { hour: '04:00', conversations: 2, avgResponseTime: 1.2 },
  { hour: '06:00', conversations: 8, avgResponseTime: 2.1 },
  { hour: '08:00', conversations: 25, avgResponseTime: 2.8 },
  { hour: '10:00', conversations: 35, avgResponseTime: 3.2 },
  { hour: '12:00', conversations: 42, avgResponseTime: 3.5 },
  { hour: '14:00', conversations: 38, avgResponseTime: 3.1 },
  { hour: '16:00', conversations: 31, avgResponseTime: 2.9 },
  { hour: '18:00', conversations: 28, avgResponseTime: 2.6 },
  { hour: '20:00', conversations: 18, avgResponseTime: 2.3 },
  { hour: '22:00', conversations: 12, avgResponseTime: 2.0 },
]

export function Analytics() {
  const [timeRange, setTimeRange] = useState('7d')
  const [metrics, setMetrics] = useState({
    totalConversations: 0,
    resolutionRate: 0,
    avgResponseTime: 0,
    customerSatisfaction: 0,
    escalationRate: 0,
    activeUsers: 0
  })

  useEffect(() => {
    // Simulate loading analytics data
    setMetrics({
      totalConversations: 1247,
      resolutionRate: 94.2,
      avgResponseTime: 2.3,
      customerSatisfaction: 4.6,
      escalationRate: 5.8,
      activeUsers: 89
    })
  }, [timeRange])

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4 text-green-500" />
      case 'down':
        return <TrendingDown className="h-4 w-4 text-red-500" />
      default:
        return <div className="h-4 w-4" />
    }
  }

  const getTrendColor = (trend) => {
    switch (trend) {
      case 'up':
        return 'text-green-600'
      case 'down':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Analytics</h1>
          <p className="text-muted-foreground">
            Detailed insights into your AI assistant performance
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select time range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Conversations</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.totalConversations.toLocaleString()}</div>
            <p className="text-xs text-green-600 flex items-center">
              <TrendingUp className="h-3 w-3 mr-1" />
              +12% from last period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Resolution Rate</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.resolutionRate}%</div>
            <p className="text-xs text-green-600 flex items-center">
              <TrendingUp className="h-3 w-3 mr-1" />
              +2.1% from last period
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
            <p className="text-xs text-green-600 flex items-center">
              <TrendingDown className="h-3 w-3 mr-1" />
              -0.3s from last period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Customer Satisfaction</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.customerSatisfaction}/5.0</div>
            <p className="text-xs text-green-600 flex items-center">
              <TrendingUp className="h-3 w-3 mr-1" />
              +0.2 from last period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Escalation Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.escalationRate}%</div>
            <p className="text-xs text-red-600 flex items-center">
              <TrendingUp className="h-3 w-3 mr-1" />
              +0.5% from last period
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
            <p className="text-xs text-green-600 flex items-center">
              <TrendingUp className="h-3 w-3 mr-1" />
              +5% from yesterday
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Analytics Tabs */}
      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="intents">Intent Analysis</TabsTrigger>
          <TabsTrigger value="satisfaction">Customer Satisfaction</TabsTrigger>
          <TabsTrigger value="patterns">Usage Patterns</TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Conversation Trends */}
            <Card>
              <CardHeader>
                <CardTitle>Conversation Volume</CardTitle>
                <CardDescription>Daily conversation trends and resolution rates</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={performanceData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <YAxis />
                    <Tooltip labelFormatter={(value) => new Date(value).toLocaleDateString()} />
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

            {/* Response Time Trends */}
            <Card>
              <CardHeader>
                <CardTitle>Response Time Trends</CardTitle>
                <CardDescription>Average response time over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={performanceData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <YAxis />
                    <Tooltip labelFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <Area 
                      type="monotone" 
                      dataKey="avgResponseTime" 
                      stroke="#8884d8" 
                      fill="#8884d8" 
                      fillOpacity={0.3}
                      name="Avg Response Time (s)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="intents" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                      data={intentAnalytics}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ intent, percentage }) => `${intent} ${percentage}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="count"
                    >
                      {intentAnalytics.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={`hsl(${index * 45}, 70%, 60%)`} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Intent Trends */}
            <Card>
              <CardHeader>
                <CardTitle>Intent Trends</CardTitle>
                <CardDescription>Changes in intent patterns</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {intentAnalytics.map((intent, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="flex items-center space-x-2">
                          {getTrendIcon(intent.trend)}
                          <span className="font-medium">{intent.intent}</span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className="text-sm text-muted-foreground">{intent.count} conversations</span>
                        <span className={`text-sm font-medium ${getTrendColor(intent.trend)}`}>
                          {intent.percentage}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="satisfaction" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Satisfaction Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Customer Satisfaction Ratings</CardTitle>
                <CardDescription>Distribution of customer feedback ratings</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={customerSatisfactionData} layout="horizontal">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="rating" type="category" />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Satisfaction Metrics */}
            <Card>
              <CardHeader>
                <CardTitle>Satisfaction Metrics</CardTitle>
                <CardDescription>Key satisfaction indicators</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium">Overall Rating</span>
                      <span className="text-2xl font-bold">4.6/5.0</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-green-600 h-2 rounded-full" style={{ width: '92%' }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium">Response Rate</span>
                      <span className="text-lg font-semibold">78.3%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full" style={{ width: '78%' }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium">Positive Feedback</span>
                      <span className="text-lg font-semibold">85%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-green-600 h-2 rounded-full" style={{ width: '85%' }} />
                    </div>
                  </div>

                  <div className="pt-4 border-t">
                    <h4 className="font-medium mb-2">Recent Feedback</h4>
                    <div className="space-y-2 text-sm">
                      <p className="text-muted-foreground">"Quick and helpful responses!"</p>
                      <p className="text-muted-foreground">"Solved my issue immediately."</p>
                      <p className="text-muted-foreground">"Very satisfied with the service."</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="patterns" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Hourly Usage Patterns</CardTitle>
              <CardDescription>Conversation volume and response times throughout the day</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={hourlyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="hour" />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="left" dataKey="conversations" fill="#8884d8" name="Conversations" />
                  <Line 
                    yAxisId="right" 
                    type="monotone" 
                    dataKey="avgResponseTime" 
                    stroke="#82ca9d" 
                    strokeWidth={2}
                    name="Avg Response Time (s)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

