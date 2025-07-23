import { useState, useEffect } from 'react'
import { 
  Search, 
  Plus, 
  BookOpen, 
  FileText, 
  Edit, 
  Trash2, 
  Upload,
  Download,
  Tag,
  Calendar
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

const mockDocuments = [
  {
    id: 'doc_001',
    title: 'Return Policy',
    content: 'Our return policy allows customers to return items within 30 days of purchase...',
    category: 'Policy',
    tags: ['returns', 'policy', 'customer service'],
    lastUpdated: '2024-01-15',
    usage: 45,
    status: 'active'
  },
  {
    id: 'doc_002',
    title: 'Shipping Information',
    content: 'We offer free shipping on orders over $50. Standard shipping takes 3-5 business days...',
    category: 'Shipping',
    tags: ['shipping', 'delivery', 'logistics'],
    lastUpdated: '2024-01-12',
    usage: 38,
    status: 'active'
  },
  {
    id: 'doc_003',
    title: 'Product Care Instructions',
    content: 'To maintain the quality of your products, please follow these care instructions...',
    category: 'Product Info',
    tags: ['care', 'maintenance', 'products'],
    lastUpdated: '2024-01-10',
    usage: 22,
    status: 'active'
  },
  {
    id: 'doc_004',
    title: 'Size Guide',
    content: 'Use our comprehensive size guide to find the perfect fit for your clothing items...',
    category: 'Product Info',
    tags: ['sizing', 'fit', 'clothing'],
    lastUpdated: '2024-01-08',
    usage: 67,
    status: 'active'
  }
]

const categories = ['All', 'Policy', 'Shipping', 'Product Info', 'FAQ', 'Troubleshooting']

export function KnowledgeBase() {
  const [documents, setDocuments] = useState([])
  const [filteredDocuments, setFilteredDocuments] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [editingDocument, setEditingDocument] = useState(null)
  const [newDocument, setNewDocument] = useState({
    title: '',
    content: '',
    category: '',
    tags: ''
  })

  useEffect(() => {
    setDocuments(mockDocuments)
    setFilteredDocuments(mockDocuments)
  }, [])

  useEffect(() => {
    let filtered = documents

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(doc => 
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))
      )
    }

    // Apply category filter
    if (selectedCategory !== 'All') {
      filtered = filtered.filter(doc => doc.category === selectedCategory)
    }

    setFilteredDocuments(filtered)
  }, [documents, searchTerm, selectedCategory])

  const handleAddDocument = () => {
    const doc = {
      id: `doc_${Date.now()}`,
      title: newDocument.title,
      content: newDocument.content,
      category: newDocument.category,
      tags: newDocument.tags.split(',').map(tag => tag.trim()),
      lastUpdated: new Date().toISOString().split('T')[0],
      usage: 0,
      status: 'active'
    }

    setDocuments([...documents, doc])
    setNewDocument({ title: '', content: '', category: '', tags: '' })
    setIsAddDialogOpen(false)
  }

  const handleEditDocument = (doc) => {
    setEditingDocument(doc)
    setNewDocument({
      title: doc.title,
      content: doc.content,
      category: doc.category,
      tags: doc.tags.join(', ')
    })
  }

  const handleUpdateDocument = () => {
    const updatedDocuments = documents.map(doc => 
      doc.id === editingDocument.id 
        ? {
            ...doc,
            title: newDocument.title,
            content: newDocument.content,
            category: newDocument.category,
            tags: newDocument.tags.split(',').map(tag => tag.trim()),
            lastUpdated: new Date().toISOString().split('T')[0]
          }
        : doc
    )

    setDocuments(updatedDocuments)
    setEditingDocument(null)
    setNewDocument({ title: '', content: '', category: '', tags: '' })
  }

  const handleDeleteDocument = (docId) => {
    setDocuments(documents.filter(doc => doc.id !== docId))
  }

  const DocumentForm = () => (
    <div className="space-y-4">
      <div>
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          value={newDocument.title}
          onChange={(e) => setNewDocument({ ...newDocument, title: e.target.value })}
          placeholder="Enter document title"
        />
      </div>

      <div>
        <Label htmlFor="category">Category</Label>
        <Select value={newDocument.category} onValueChange={(value) => setNewDocument({ ...newDocument, category: value })}>
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

      <div>
        <Label htmlFor="tags">Tags (comma-separated)</Label>
        <Input
          id="tags"
          value={newDocument.tags}
          onChange={(e) => setNewDocument({ ...newDocument, tags: e.target.value })}
          placeholder="tag1, tag2, tag3"
        />
      </div>

      <div>
        <Label htmlFor="content">Content</Label>
        <Textarea
          id="content"
          value={newDocument.content}
          onChange={(e) => setNewDocument({ ...newDocument, content: e.target.value })}
          placeholder="Enter document content"
          rows={6}
        />
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Knowledge Base</h1>
          <p className="text-muted-foreground">
            Manage documents and information for your AI assistant
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
                Add Document
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add New Document</DialogTitle>
                <DialogDescription>
                  Create a new document for your knowledge base
                </DialogDescription>
              </DialogHeader>
              <DocumentForm />
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddDocument}>Add Document</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
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

      {/* Knowledge Base Tabs */}
      <Tabs defaultValue="documents" className="space-y-4">
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="space-y-4">
          {/* Documents Grid */}
          <div className="grid gap-4">
            {filteredDocuments.map((document) => (
              <Card key={document.id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <FileText className="h-5 w-5 text-muted-foreground" />
                        <h3 className="font-semibold text-lg">{document.title}</h3>
                        <Badge variant="outline">{document.category}</Badge>
                      </div>
                      
                      <p className="text-muted-foreground mb-3 line-clamp-2">
                        {document.content}
                      </p>
                      
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <div className="flex items-center space-x-1">
                          <Calendar className="h-4 w-4" />
                          <span>Updated {document.lastUpdated}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <BookOpen className="h-4 w-4" />
                          <span>{document.usage} uses</span>
                        </div>
                      </div>
                      
                      <div className="flex flex-wrap gap-1 mt-3">
                        {document.tags.map((tag, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            <Tag className="h-3 w-3 mr-1" />
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 ml-4">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleEditDocument(document)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                          <DialogHeader>
                            <DialogTitle>Edit Document</DialogTitle>
                            <DialogDescription>
                              Update the document information
                            </DialogDescription>
                          </DialogHeader>
                          <DocumentForm />
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setEditingDocument(null)}>
                              Cancel
                            </Button>
                            <Button onClick={handleUpdateDocument}>Update Document</Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>

                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => handleDeleteDocument(document.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {filteredDocuments.length === 0 && (
            <div className="text-center py-8">
              <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No documents found</p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{documents.length}</div>
                <p className="text-xs text-muted-foreground">
                  +2 from last month
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Usage</CardTitle>
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {documents.reduce((sum, doc) => sum + doc.usage, 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  +15% from last month
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Categories</CardTitle>
                <Tag className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {new Set(documents.map(doc => doc.category)).size}
                </div>
                <p className="text-xs text-muted-foreground">
                  Active categories
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Usage</CardTitle>
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {documents.length > 0 ? Math.round(documents.reduce((sum, doc) => sum + doc.usage, 0) / documents.length) : 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  Per document
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Most Used Documents</CardTitle>
              <CardDescription>Documents with highest usage</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {documents
                  .sort((a, b) => b.usage - a.usage)
                  .slice(0, 5)
                  .map((doc, index) => (
                    <div key={doc.id} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="text-sm font-medium text-muted-foreground">
                          #{index + 1}
                        </span>
                        <div>
                          <p className="font-medium">{doc.title}</p>
                          <p className="text-sm text-muted-foreground">{doc.category}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-medium">{doc.usage} uses</p>
                        <div className="w-20 bg-gray-200 rounded-full h-2 mt-1">
                          <div 
                            className="bg-blue-600 h-2 rounded-full" 
                            style={{ width: `${(doc.usage / Math.max(...documents.map(d => d.usage))) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Knowledge Base Settings</CardTitle>
              <CardDescription>Configure your knowledge base preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Auto-sync with external sources</p>
                  <p className="text-sm text-muted-foreground">
                    Automatically update documents from connected sources
                  </p>
                </div>
                <Button variant="outline">Configure</Button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Document versioning</p>
                  <p className="text-sm text-muted-foreground">
                    Keep track of document changes and revisions
                  </p>
                </div>
                <Button variant="outline">Enable</Button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Export knowledge base</p>
                  <p className="text-sm text-muted-foreground">
                    Download all documents as a backup
                  </p>
                </div>
                <Button variant="outline">
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

