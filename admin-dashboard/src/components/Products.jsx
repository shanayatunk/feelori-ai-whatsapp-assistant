import { useState, useEffect } from 'react'
import { 
  Search, 
  Plus, 
  Package, 
  Edit, 
  Trash2, 
  Upload,
  Download,
  Tag,
  DollarSign,
  TrendingUp,
  AlertTriangle
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const mockProducts = [
  {
    id: 'prod_001',
    name: 'Blue T-Shirt',
    description: 'Comfortable cotton t-shirt in blue color',
    price: 29.99,
    category: 'Clothing',
    stock: 45,
    sku: 'TSH-BLU-001',
    status: 'active',
    tags: ['clothing', 'casual', 'cotton'],
    images: ['https://via.placeholder.com/300x300?text=Blue+T-Shirt'],
    lastUpdated: '2024-01-15',
    sales: 156
  },
  {
    id: 'prod_002',
    name: 'Red Dress',
    description: 'Elegant red dress for special occasions',
    price: 89.99,
    category: 'Clothing',
    stock: 23,
    sku: 'DRS-RED-001',
    status: 'active',
    tags: ['clothing', 'formal', 'dress'],
    images: ['https://via.placeholder.com/300x300?text=Red+Dress'],
    lastUpdated: '2024-01-14',
    sales: 89
  },
  {
    id: 'prod_003',
    name: 'Sneakers',
    description: 'Comfortable running sneakers',
    price: 129.99,
    category: 'Footwear',
    stock: 8,
    sku: 'SNK-WHT-001',
    status: 'low_stock',
    tags: ['footwear', 'sports', 'running'],
    images: ['https://via.placeholder.com/300x300?text=Sneakers'],
    lastUpdated: '2024-01-13',
    sales: 234
  },
  {
    id: 'prod_004',
    name: 'Hat',
    description: 'Stylish hat for outdoor activities',
    price: 29.99,
    category: 'Accessories',
    stock: 0,
    sku: 'HAT-BLK-001',
    status: 'out_of_stock',
    tags: ['accessories', 'outdoor', 'style'],
    images: ['https://via.placeholder.com/300x300?text=Hat'],
    lastUpdated: '2024-01-12',
    sales: 67
  }
]

const categories = ['All', 'Clothing', 'Footwear', 'Accessories', 'Electronics']

export function Products() {
  const [products, setProducts] = useState([])
  const [filteredProducts, setFilteredProducts] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [newProduct, setNewProduct] = useState({
    name: '',
    description: '',
    price: '',
    category: '',
    stock: '',
    sku: '',
    tags: ''
  })

  useEffect(() => {
    setProducts(mockProducts)
    setFilteredProducts(mockProducts)
  }, [])

  useEffect(() => {
    let filtered = products

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(product => 
        product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))
      )
    }

    // Apply category filter
    if (selectedCategory !== 'All') {
      filtered = filtered.filter(product => product.category === selectedCategory)
    }

    setFilteredProducts(filtered)
  }, [products, searchTerm, selectedCategory])

  const getStatusColor = (status) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'low_stock':
        return 'bg-yellow-500'
      case 'out_of_stock':
        return 'bg-red-500'
      case 'inactive':
        return 'bg-gray-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active':
        return <Package className="h-4 w-4" />
      case 'low_stock':
        return <AlertTriangle className="h-4 w-4" />
      case 'out_of_stock':
        return <AlertTriangle className="h-4 w-4" />
      default:
        return <Package className="h-4 w-4" />
    }
  }

  const handleAddProduct = () => {
    const product = {
      id: `prod_${Date.now()}`,
      name: newProduct.name,
      description: newProduct.description,
      price: parseFloat(newProduct.price),
      category: newProduct.category,
      stock: parseInt(newProduct.stock),
      sku: newProduct.sku,
      status: parseInt(newProduct.stock) > 10 ? 'active' : parseInt(newProduct.stock) > 0 ? 'low_stock' : 'out_of_stock',
      tags: newProduct.tags.split(',').map(tag => tag.trim()),
      images: ['https://via.placeholder.com/300x300?text=' + encodeURIComponent(newProduct.name)],
      lastUpdated: new Date().toISOString().split('T')[0],
      sales: 0
    }

    setProducts([...products, product])
    setNewProduct({ name: '', description: '', price: '', category: '', stock: '', sku: '', tags: '' })
    setIsAddDialogOpen(false)
  }

  const handleEditProduct = (product) => {
    setEditingProduct(product)
    setNewProduct({
      name: product.name,
      description: product.description,
      price: product.price.toString(),
      category: product.category,
      stock: product.stock.toString(),
      sku: product.sku,
      tags: product.tags.join(', ')
    })
  }

  const handleUpdateProduct = () => {
    const updatedProducts = products.map(product => 
      product.id === editingProduct.id 
        ? {
            ...product,
            name: newProduct.name,
            description: newProduct.description,
            price: parseFloat(newProduct.price),
            category: newProduct.category,
            stock: parseInt(newProduct.stock),
            sku: newProduct.sku,
            status: parseInt(newProduct.stock) > 10 ? 'active' : parseInt(newProduct.stock) > 0 ? 'low_stock' : 'out_of_stock',
            tags: newProduct.tags.split(',').map(tag => tag.trim()),
            lastUpdated: new Date().toISOString().split('T')[0]
          }
        : product
    )

    setProducts(updatedProducts)
    setEditingProduct(null)
    setNewProduct({ name: '', description: '', price: '', category: '', stock: '', sku: '', tags: '' })
  }

  const handleDeleteProduct = (productId) => {
    setProducts(products.filter(product => product.id !== productId))
  }

  const ProductForm = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="name">Product Name</Label>
          <Input
            id="name"
            value={newProduct.name}
            onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
            placeholder="Enter product name"
          />
        </div>
        <div>
          <Label htmlFor="sku">SKU</Label>
          <Input
            id="sku"
            value={newProduct.sku}
            onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
            placeholder="Enter SKU"
          />
        </div>
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={newProduct.description}
          onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
          placeholder="Enter product description"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label htmlFor="price">Price ($)</Label>
          <Input
            id="price"
            type="number"
            step="0.01"
            value={newProduct.price}
            onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })}
            placeholder="0.00"
          />
        </div>
        <div>
          <Label htmlFor="stock">Stock</Label>
          <Input
            id="stock"
            type="number"
            value={newProduct.stock}
            onChange={(e) => setNewProduct({ ...newProduct, stock: e.target.value })}
            placeholder="0"
          />
        </div>
        <div>
          <Label htmlFor="category">Category</Label>
          <Select value={newProduct.category} onValueChange={(value) => setNewProduct({ ...newProduct, category: value })}>
            <SelectTrigger>
              <SelectValue placeholder="Select category" />
            </SelectTrigger>
            <SelectContent>
              {categories.filter(cat => cat !== 'All').map(category => (
                <SelectItem key={category} value={category}>{category}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="tags">Tags (comma-separated)</Label>
        <Input
          id="tags"
          value={newProduct.tags}
          onChange={(e) => setNewProduct({ ...newProduct, tags: e.target.value })}
          placeholder="tag1, tag2, tag3"
        />
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Products</h1>
          <p className="text-muted-foreground">
            Manage your product catalog and inventory
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline">
            <Upload className="h-4 w-4 mr-2" />
            Import
          </Button>
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Product
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add New Product</DialogTitle>
                <DialogDescription>
                  Create a new product for your catalog
                </DialogDescription>
              </DialogHeader>
              <ProductForm />
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddProduct}>Add Product</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Product Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Products</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{products.length}</div>
            <p className="text-xs text-muted-foreground">
              +2 from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Low Stock</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {products.filter(product => product.status === 'low_stock' || product.status === 'out_of_stock').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Require attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${products.reduce((sum, product) => sum + (product.price * product.stock), 0).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              Inventory value
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Price</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${products.length > 0 ? (products.reduce((sum, product) => sum + product.price, 0) / products.length).toFixed(2) : '0.00'}
            </div>
            <p className="text-xs text-muted-foreground">
              Per product
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search products..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by category" />
              </SelectTrigger>
              <SelectContent>
                {categories.map(category => (
                  <SelectItem key={category} value={category}>{category}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Products Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Products</TabsTrigger>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="low_stock">Low Stock</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-4">
          {/* Products Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProducts.map((product) => (
              <Card key={product.id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="space-y-4">
                    {/* Product Image */}
                    <div className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                      <Package className="h-12 w-12 text-muted-foreground" />
                    </div>

                    {/* Product Info */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-lg">{product.name}</h3>
                        <Badge className={getStatusColor(product.status)}>
                          {getStatusIcon(product.status)}
                          <span className="ml-1">{product.status.replace('_', ' ')}</span>
                        </Badge>
                      </div>
                      
                      <p className="text-muted-foreground text-sm mb-3 line-clamp-2">
                        {product.description}
                      </p>
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Price</p>
                          <p className="font-semibold text-lg">${product.price}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Stock</p>
                          <p className="font-semibold">{product.stock} units</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">SKU</p>
                          <p className="font-medium">{product.sku}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Sales</p>
                          <p className="font-medium">{product.sales}</p>
                        </div>
                      </div>
                      
                      <div className="flex flex-wrap gap-1 mt-3">
                        {product.tags.map((tag, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            <Tag className="h-3 w-3 mr-1" />
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex space-x-2">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="flex-1"
                            onClick={() => handleEditProduct(product)}
                          >
                            <Edit className="h-4 w-4 mr-1" />
                            Edit
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                          <DialogHeader>
                            <DialogTitle>Edit Product</DialogTitle>
                            <DialogDescription>
                              Update the product information
                            </DialogDescription>
                          </DialogHeader>
                          <ProductForm />
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setEditingProduct(null)}>
                              Cancel
                            </Button>
                            <Button onClick={handleUpdateProduct}>Update Product</Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>

                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeleteProduct(product.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {filteredProducts.length === 0 && (
            <div className="text-center py-8">
              <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No products found</p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="active">
          <div className="text-center py-8">
            <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Active products will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="low_stock">
          <div className="text-center py-8">
            <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Low stock products will appear here</p>
          </div>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Top Selling Products</CardTitle>
              <CardDescription>Products with highest sales</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {products
                  .sort((a, b) => b.sales - a.sales)
                  .slice(0, 5)
                  .map((product, index) => (
                    <div key={product.id} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="text-sm font-medium text-muted-foreground">
                          #{index + 1}
                        </span>
                        <div>
                          <p className="font-medium">{product.name}</p>
                          <p className="text-sm text-muted-foreground">{product.category}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-medium">{product.sales} sold</p>
                        <p className="text-sm text-muted-foreground">${(product.sales * product.price).toFixed(2)} revenue</p>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

