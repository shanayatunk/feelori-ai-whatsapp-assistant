import { useState, useEffect } from 'react'
import { 
  Search, 
  Filter, 
  MessageSquare, 
  User, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  MoreHorizontal,
  Eye,
  UserPlus
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

const mockConversations = [
  {
    id: 'conv_001',
    customer: {
      name: 'John Doe',
      phone: '+1234567890',
      email: 'john@example.com'
    },
    status: 'active',
    intent: 'product_query',
    sentiment: 'positive',
    lastMessage: 'I\'m looking for a blue t-shirt in size M',
    lastActivity: '2 minutes ago',
    messageCount: 5,
    escalated: false,
    aiConfidence: 0.92
  },
  {
    id: 'conv_002',
    customer: {
      name: 'Jane Smith',
      phone: '+1234567891',
      email: 'jane@example.com'
    },
    status: 'resolved',
    intent: 'order_status',
    sentiment: 'neutral',
    lastMessage: 'Thank you for the tracking information!',
    lastActivity: '15 minutes ago',
    messageCount: 8,
    escalated: false,
    aiConfidence: 0.88
  },
  {
    id: 'conv_003',
    customer: {
      name: 'Bob Johnson',
      phone: '+1234567892',
      email: 'bob@example.com'
    },
    status: 'escalated',
    intent: 'policy_query',
    sentiment: 'negative',
    lastMessage: 'This is unacceptable, I want to speak to a manager',
    lastActivity: '5 minutes ago',
    messageCount: 12,
    escalated: true,
    aiConfidence: 0.45
  },
  {
    id: 'conv_004',
    customer: {
      name: 'Alice Brown',
      phone: '+1234567893',
      email: 'alice@example.com'
    },
    status: 'pending',
    intent: 'general',
    sentiment: 'positive',
    lastMessage: 'Hello, I need help with my account',
    lastActivity: '1 hour ago',
    messageCount: 2,
    escalated: false,
    aiConfidence: 0.76
  }
]

export function Conversations() {
  const [conversations, setConversations] = useState([])
  const [filteredConversations, setFilteredConversations] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedConversation, setSelectedConversation] = useState(null)

  useEffect(() => {
    // Simulate loading conversations
    setConversations(mockConversations)
    setFilteredConversations(mockConversations)
  }, [])

  useEffect(() => {
    let filtered = conversations

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(conv => 
        conv.customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        conv.customer.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        conv.lastMessage.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(conv => conv.status === statusFilter)
    }

    setFilteredConversations(filtered)
  }, [conversations, searchTerm, statusFilter])

  const getStatusColor = (status) => {
    switch (status) {
      case 'active':
        return 'bg-blue-500'
      case 'resolved':
        return 'bg-green-500'
      case 'escalated':
        return 'bg-red-500'
      case 'pending':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive':
        return 'text-green-600'
      case 'negative':
        return 'text-red-600'
      case 'neutral':
        return 'text-gray-600'
      default:
        return 'text-gray-600'
    }
  }

  const getIntentBadgeColor = (intent) => {
    switch (intent) {
      case 'product_query':
        return 'bg-blue-100 text-blue-800'
      case 'order_status':
        return 'bg-green-100 text-green-800'
      case 'policy_query':
        return 'bg-purple-100 text-purple-800'
      case 'general':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const ConversationDetail = ({ conversation }) => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{conversation.customer.name}</h3>
          <p className="text-sm text-muted-foreground">{conversation.customer.email}</p>
        </div>
        <Badge className={getStatusColor(conversation.status)}>
          {conversation.status}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm font-medium">Intent</p>
          <Badge className={getIntentBadgeColor(conversation.intent)}>
            {conversation.intent.replace('_', ' ')}
          </Badge>
        </div>
        <div>
          <p className="text-sm font-medium">Sentiment</p>
          <p className={`text-sm ${getSentimentColor(conversation.sentiment)}`}>
            {conversation.sentiment}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium">AI Confidence</p>
          <p className="text-sm">{(conversation.aiConfidence * 100).toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-sm font-medium">Messages</p>
          <p className="text-sm">{conversation.messageCount}</p>
        </div>
      </div>

      <div>
        <p className="text-sm font-medium mb-2">Last Message</p>
        <div className="bg-muted p-3 rounded-lg">
          <p className="text-sm">{conversation.lastMessage}</p>
          <p className="text-xs text-muted-foreground mt-1">{conversation.lastActivity}</p>
        </div>
      </div>

      <div className="flex space-x-2">
        <Button size="sm">View Full Conversation</Button>
        <Button size="sm" variant="outline">Escalate to Human</Button>
        {conversation.status === 'active' && (
          <Button size="sm" variant="outline">Mark Resolved</Button>
        )}
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Conversations</h1>
        <p className="text-muted-foreground">
          Monitor and manage customer conversations with your AI assistant
        </p>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search conversations..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Conversation Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Conversations</TabsTrigger>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="escalated">Escalated</TabsTrigger>
          <TabsTrigger value="resolved">Resolved</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-4">
          {/* Conversation List */}
          <div className="grid gap-4">
            {filteredConversations.map((conversation) => (
              <Card key={conversation.id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`w-3 h-3 rounded-full ${getStatusColor(conversation.status)}`} />
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="font-semibold">{conversation.customer.name}</h3>
                          {conversation.escalated && (
                            <AlertCircle className="h-4 w-4 text-red-500" />
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {conversation.customer.phone}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <Badge className={getIntentBadgeColor(conversation.intent)}>
                          {conversation.intent.replace('_', ' ')}
                        </Badge>
                        <p className="text-xs text-muted-foreground mt-1">
                          {conversation.messageCount} messages
                        </p>
                      </div>

                      <div className="text-right">
                        <p className={`text-sm font-medium ${getSentimentColor(conversation.sentiment)}`}>
                          {conversation.sentiment}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {conversation.lastActivity}
                        </p>
                      </div>

                      <Dialog>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                          <DialogHeader>
                            <DialogTitle>Conversation Details</DialogTitle>
                            <DialogDescription>
                              View and manage conversation with {conversation.customer.name}
                            </DialogDescription>
                          </DialogHeader>
                          <ConversationDetail conversation={conversation} />
                        </DialogContent>
                      </Dialog>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>View Details</DropdownMenuItem>
                          <DropdownMenuItem>Escalate to Human</DropdownMenuItem>
                          <DropdownMenuItem>Mark as Resolved</DropdownMenuItem>
                          <DropdownMenuItem>Export Conversation</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-sm text-muted-foreground">
                      <strong>Last message:</strong> {conversation.lastMessage}
                    </p>
                    <div className="flex items-center justify-between mt-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-muted-foreground">AI Confidence:</span>
                        <div className="w-20 bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full" 
                            style={{ width: `${conversation.aiConfidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {(conversation.aiConfidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <Badge variant="outline" className={getStatusColor(conversation.status)}>
                        {conversation.status}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Other tab contents would filter the conversations accordingly */}
        <TabsContent value="active">
          <div className="text-center py-8">
            <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Active conversations will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="escalated">
          <div className="text-center py-8">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Escalated conversations will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="resolved">
          <div className="text-center py-8">
            <CheckCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Resolved conversations will appear here</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

