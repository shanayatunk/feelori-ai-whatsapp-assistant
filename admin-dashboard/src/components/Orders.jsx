import { useState, useEffect } from 'react'
import { 
  Search, 
  Filter, 
  ShoppingCart, 
  Package, 
  Truck, 
  CheckCircle, 
  AlertCircle,
  MoreHorizontal,
  Eye,
  RefreshCw,
  Download
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

const mockOrders = [
  {
    id: 'ORD001',
    orderNumber: '#1001',
    customer: {
      name: 'John Doe',
      email: 'john@example.com',
      phone: '+1234567890'
    },
    status: 'processing',
    total: 129.99,
    items: [
      { name: 'Blue T-Shirt', quantity: 2, price: 29.99 },
      { name: 'Jeans', quantity: 1, price: 69.99 }
    ],
    shippingAddress: '123 Main St, Anytown, ST 12345',
    orderDate: '2024-01-15T10:30:00Z',
    estimatedDelivery: '2024-01-20',
    trackingNumber: 'TRK123456789',
    paymentStatus: 'paid'
  },
  {
    id: 'ORD002',
    orderNumber: '#1002',
    customer: {
      name: 'Jane Smith',
      email: 'jane@example.com',
      phone: '+1234567891'
    },
    status: 'shipped',
    total: 89.99,
    items: [
      { name: 'Red Dress', quantity: 1, price: 89.99 }
    ],
    shippingAddress: '456 Oak Ave, Another City, ST 67890',
    orderDate: '2024-01-14T14:20:00Z',
    estimatedDelivery: '2024-01-19',
    trackingNumber: 'TRK987654321',
    paymentStatus: 'paid'
  },
  {
    id: 'ORD003',
    orderNumber: '#1003',
    customer: {
      name: 'Bob Johnson',
      email: 'bob@example.com',
      phone: '+1234567892'
    },
    status: 'pending',
    total: 199.99,
    items: [
      { name: 'Sneakers', quantity: 1, price: 129.99 },
      { name: 'Socks', quantity: 2, price: 34.99 }
    ],
    shippingAddress: '789 Pine St, Third Town, ST 13579',
    orderDate: '2024-01-16T09:15:00Z',
    estimatedDelivery: '2024-01-22',
    trackingNumber: null,
    paymentStatus: 'pending'
  },
  {
    id: 'ORD004',
    orderNumber: '#1004',
    customer: {
      name: 'Alice Brown',
      email: 'alice@example.com',
      phone: '+1234567893'
    },
    status: 'delivered',
    total: 59.99,
    items: [
      { name: 'Hat', quantity: 1, price: 29.99 },
      { name: 'Scarf', quantity: 1, price: 29.99 }
    ],
    shippingAddress: '321 Elm Dr, Fourth City, ST 24680',
    orderDate: '2024-01-12T16:45:00Z',
    estimatedDelivery: '2024-01-17',
    trackingNumber: 'TRK456789123',
    paymentStatus: 'paid'
  }
]

export function Orders() {
  const [orders, setOrders] = useState([])
  const [filteredOrders, setFilteredOrders] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedOrder, setSelectedOrder] = useState(null)

  useEffect(() => {
    setOrders(mockOrders)
    setFilteredOrders(mockOrders)
  }, [])

  useEffect(() => {
    let filtered = orders

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(order => 
        order.orderNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
        order.customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        order.customer.email.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(order => order.status === statusFilter)
    }

    setFilteredOrders(filtered)
  }, [orders, searchTerm, statusFilter])

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-500'
      case 'processing':
        return 'bg-blue-500'
      case 'shipped':
        return 'bg-purple-500'
      case 'delivered':
        return 'bg-green-500'
      case 'cancelled':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return <AlertCircle className="h-4 w-4" />
      case 'processing':
        return <RefreshCw className="h-4 w-4" />
      case 'shipped':
        return <Truck className="h-4 w-4" />
      case 'delivered':
        return <CheckCircle className="h-4 w-4" />
      default:
        return <Package className="h-4 w-4" />
    }
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const OrderDetail = ({ order }) => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{order.orderNumber}</h3>
          <p className="text-sm text-muted-foreground">
            Ordered on {formatDate(order.orderDate)}
          </p>
        </div>
        <Badge className={getStatusColor(order.status)}>
          {getStatusIcon(order.status)}
          <span className="ml-1">{order.status}</span>
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="font-medium mb-2">Customer Information</h4>
          <div className="space-y-1 text-sm">
            <p><strong>Name:</strong> {order.customer.name}</p>
            <p><strong>Email:</strong> {order.customer.email}</p>
            <p><strong>Phone:</strong> {order.customer.phone}</p>
          </div>
        </div>

        <div>
          <h4 className="font-medium mb-2">Shipping Address</h4>
          <p className="text-sm">{order.shippingAddress}</p>
        </div>

        <div>
          <h4 className="font-medium mb-2">Payment Information</h4>
          <div className="space-y-1 text-sm">
            <p><strong>Status:</strong> 
              <Badge variant={order.paymentStatus === 'paid' ? 'default' : 'destructive'} className="ml-2">
                {order.paymentStatus}
              </Badge>
            </p>
            <p><strong>Total:</strong> ${order.total}</p>
          </div>
        </div>

        <div>
          <h4 className="font-medium mb-2">Shipping Information</h4>
          <div className="space-y-1 text-sm">
            <p><strong>Estimated Delivery:</strong> {order.estimatedDelivery}</p>
            {order.trackingNumber && (
              <p><strong>Tracking:</strong> {order.trackingNumber}</p>
            )}
          </div>
        </div>
      </div>

      <div>
        <h4 className="font-medium mb-2">Order Items</h4>
        <div className="space-y-2">
          {order.items.map((item, index) => (
            <div key={index} className="flex justify-between items-center p-3 bg-muted rounded-lg">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">Quantity: {item.quantity}</p>
              </div>
              <p className="font-medium">${item.price}</p>
            </div>
          ))}
        </div>
        <div className="flex justify-between items-center mt-4 pt-4 border-t">
          <p className="font-semibold">Total</p>
          <p className="font-semibold text-lg">${order.total}</p>
        </div>
      </div>

      <div className="flex space-x-2">
        <Button size="sm">Update Status</Button>
        <Button size="sm" variant="outline">Send Notification</Button>
        <Button size="sm" variant="outline">Print Invoice</Button>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Orders</h1>
          <p className="text-muted-foreground">
            Manage and track customer orders
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button>
            <RefreshCw className="h-4 w-4 mr-2" />
            Sync Orders
          </Button>
        </div>
      </div>

      {/* Order Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Orders</CardTitle>
            <ShoppingCart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{orders.length}</div>
            <p className="text-xs text-muted-foreground">
              +12% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Orders</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {orders.filter(order => order.status === 'pending').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Require attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Revenue</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${orders.reduce((sum, order) => sum + order.total, 0).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              +8% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Order Value</CardTitle>
            <Truck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${orders.length > 0 ? (orders.reduce((sum, order) => sum + order.total, 0) / orders.length).toFixed(2) : '0.00'}
            </div>
            <p className="text-xs text-muted-foreground">
              +5% from last month
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search orders..."
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
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="shipped">Shipped</SelectItem>
                <SelectItem value="delivered">Delivered</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Orders Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Orders</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="processing">Processing</TabsTrigger>
          <TabsTrigger value="shipped">Shipped</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-4">
          {/* Orders List */}
          <div className="grid gap-4">
            {filteredOrders.map((order) => (
              <Card key={order.id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2 rounded-full ${getStatusColor(order.status)}`}>
                        <div className="text-white">
                          {getStatusIcon(order.status)}
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="font-semibold">{order.orderNumber}</h3>
                          <Badge variant="outline">{order.status}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {order.customer.name} • {order.customer.email}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <p className="font-semibold">${order.total}</p>
                        <p className="text-xs text-muted-foreground">
                          {order.items.length} item{order.items.length !== 1 ? 's' : ''}
                        </p>
                      </div>

                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {formatDate(order.orderDate)}
                        </p>
                        {order.trackingNumber && (
                          <p className="text-xs text-muted-foreground">
                            {order.trackingNumber}
                          </p>
                        )}
                      </div>

                      <Dialog>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-4xl">
                          <DialogHeader>
                            <DialogTitle>Order Details</DialogTitle>
                            <DialogDescription>
                              Complete information for order {order.orderNumber}
                            </DialogDescription>
                          </DialogHeader>
                          <OrderDetail order={order} />
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
                          <DropdownMenuItem>Update Status</DropdownMenuItem>
                          <DropdownMenuItem>Send Notification</DropdownMenuItem>
                          <DropdownMenuItem>Print Invoice</DropdownMenuItem>
                          <DropdownMenuItem>Cancel Order</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t">
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <span className="text-muted-foreground">Items: </span>
                        {order.items.map(item => item.name).join(', ')}
                      </div>
                      <div>
                        <span className="text-muted-foreground">Delivery: </span>
                        {order.estimatedDelivery}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Other tab contents would filter the orders accordingly */}
        <TabsContent value="pending">
          <div className="text-center py-8">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Pending orders will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="processing">
          <div className="text-center py-8">
            <RefreshCw className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Processing orders will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="shipped">
          <div className="text-center py-8">
            <Truck className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Shipped orders will appear here</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

