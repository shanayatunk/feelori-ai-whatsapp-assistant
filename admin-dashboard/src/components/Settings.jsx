import { useState } from 'react'
import { 
  Settings as SettingsIcon, 
  Bot, 
  MessageSquare, 
  Bell, 
  Shield, 
  Database,
  Zap,
  Users,
  Globe,
  Save,
  RefreshCw
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'

export function Settings() {
  const [settings, setSettings] = useState({
    // AI Configuration
    aiModel: 'gpt-4',
    aiTemperature: 0.7,
    maxTokens: 2048,
    systemPrompt: 'You are a helpful AI assistant for an e-commerce store.',
    
    // WhatsApp Configuration
    whatsappPhoneNumber: '+1234567890',
    whatsappApiKey: '',
    whatsappWebhookUrl: '',
    
    // Notifications
    emailNotifications: true,
    smsNotifications: false,
    pushNotifications: true,
    escalationNotifications: true,
    
    // Business Hours
    businessHoursEnabled: true,
    businessStartTime: '09:00',
    businessEndTime: '17:00',
    timezone: 'America/New_York',
    
    // Auto-responses
    autoResponseEnabled: true,
    autoResponseDelay: 2,
    escalationThreshold: 3,
    
    // Security
    twoFactorAuth: false,
    sessionTimeout: 30,
    ipWhitelist: '',
    
    // Integrations
    shopifyApiKey: '',
    shopifyStoreUrl: '',
    shippingApiKey: '',
    analyticsEnabled: true
  })

  const [isSaving, setIsSaving] = useState(false)

  const handleSettingChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }))
  }

  const handleSaveSettings = async () => {
    setIsSaving(true)
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsSaving(false)
    // Show success message
  }

  const SettingItem = ({ icon: Icon, title, description, children }) => (
    <div className="flex items-center justify-between py-4">
      <div className="flex items-center space-x-3">
        <Icon className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium">{title}</p>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div>{children}</div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Settings</h1>
          <p className="text-muted-foreground">
            Configure your AI assistant and system preferences
          </p>
        </div>
        <Button onClick={handleSaveSettings} disabled={isSaving}>
          {isSaving ? (
            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      {/* Settings Tabs */}
      <Tabs defaultValue="ai" className="space-y-4">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="ai">AI Config</TabsTrigger>
          <TabsTrigger value="whatsapp">WhatsApp</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="business">Business</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
        </TabsList>

        {/* AI Configuration */}
        <TabsContent value="ai" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Bot className="h-5 w-5" />
                <span>AI Model Configuration</span>
              </CardTitle>
              <CardDescription>
                Configure the AI model and behavior settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="aiModel">AI Model</Label>
                  <Select value={settings.aiModel} onValueChange={(value) => handleSettingChange('aiModel', value)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gpt-4">GPT-4</SelectItem>
                      <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                      <SelectItem value="claude-3">Claude 3</SelectItem>
                      <SelectItem value="gemini-pro">Gemini Pro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="maxTokens">Max Tokens</Label>
                  <Input
                    id="maxTokens"
                    type="number"
                    value={settings.maxTokens}
                    onChange={(e) => handleSettingChange('maxTokens', parseInt(e.target.value))}
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="aiTemperature">Temperature: {settings.aiTemperature}</Label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.aiTemperature}
                  onChange={(e) => handleSettingChange('aiTemperature', parseFloat(e.target.value))}
                  className="w-full mt-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Conservative</span>
                  <span>Creative</span>
                </div>
              </div>

              <div>
                <Label htmlFor="systemPrompt">System Prompt</Label>
                <Textarea
                  id="systemPrompt"
                  value={settings.systemPrompt}
                  onChange={(e) => handleSettingChange('systemPrompt', e.target.value)}
                  rows={4}
                  placeholder="Enter the system prompt for the AI assistant"
                />
              </div>

              <Separator />

              <div className="space-y-4">
                <h4 className="font-medium">Response Behavior</h4>
                
                <SettingItem
                  icon={Zap}
                  title="Auto-response"
                  description="Automatically respond to customer messages"
                >
                  <Switch
                    checked={settings.autoResponseEnabled}
                    onCheckedChange={(checked) => handleSettingChange('autoResponseEnabled', checked)}
                  />
                </SettingItem>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="autoResponseDelay">Response Delay (seconds)</Label>
                    <Input
                      id="autoResponseDelay"
                      type="number"
                      value={settings.autoResponseDelay}
                      onChange={(e) => handleSettingChange('autoResponseDelay', parseInt(e.target.value))}
                    />
                  </div>
                  <div>
                    <Label htmlFor="escalationThreshold">Escalation Threshold</Label>
                    <Input
                      id="escalationThreshold"
                      type="number"
                      value={settings.escalationThreshold}
                      onChange={(e) => handleSettingChange('escalationThreshold', parseInt(e.target.value))}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* WhatsApp Configuration */}
        <TabsContent value="whatsapp" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <MessageSquare className="h-5 w-5" />
                <span>WhatsApp Business API</span>
              </CardTitle>
              <CardDescription>
                Configure WhatsApp Business API connection
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="whatsappPhoneNumber">Phone Number</Label>
                <Input
                  id="whatsappPhoneNumber"
                  value={settings.whatsappPhoneNumber}
                  onChange={(e) => handleSettingChange('whatsappPhoneNumber', e.target.value)}
                  placeholder="+1234567890"
                />
              </div>

              <div>
                <Label htmlFor="whatsappApiKey">API Key</Label>
                <Input
                  id="whatsappApiKey"
                  type="password"
                  value={settings.whatsappApiKey}
                  onChange={(e) => handleSettingChange('whatsappApiKey', e.target.value)}
                  placeholder="Enter your WhatsApp API key"
                />
              </div>

              <div>
                <Label htmlFor="whatsappWebhookUrl">Webhook URL</Label>
                <Input
                  id="whatsappWebhookUrl"
                  value={settings.whatsappWebhookUrl}
                  onChange={(e) => handleSettingChange('whatsappWebhookUrl', e.target.value)}
                  placeholder="https://your-domain.com/webhook"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Button variant="outline">Test Connection</Button>
                <Button variant="outline">Verify Webhook</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications */}
        <TabsContent value="notifications" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Bell className="h-5 w-5" />
                <span>Notification Preferences</span>
              </CardTitle>
              <CardDescription>
                Configure how you receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SettingItem
                icon={Bell}
                title="Email Notifications"
                description="Receive notifications via email"
              >
                <Switch
                  checked={settings.emailNotifications}
                  onCheckedChange={(checked) => handleSettingChange('emailNotifications', checked)}
                />
              </SettingItem>

              <SettingItem
                icon={MessageSquare}
                title="SMS Notifications"
                description="Receive notifications via SMS"
              >
                <Switch
                  checked={settings.smsNotifications}
                  onCheckedChange={(checked) => handleSettingChange('smsNotifications', checked)}
                />
              </SettingItem>

              <SettingItem
                icon={Bell}
                title="Push Notifications"
                description="Receive browser push notifications"
              >
                <Switch
                  checked={settings.pushNotifications}
                  onCheckedChange={(checked) => handleSettingChange('pushNotifications', checked)}
                />
              </SettingItem>

              <SettingItem
                icon={Users}
                title="Escalation Notifications"
                description="Get notified when conversations are escalated"
              >
                <Switch
                  checked={settings.escalationNotifications}
                  onCheckedChange={(checked) => handleSettingChange('escalationNotifications', checked)}
                />
              </SettingItem>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Business Settings */}
        <TabsContent value="business" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Globe className="h-5 w-5" />
                <span>Business Hours</span>
              </CardTitle>
              <CardDescription>
                Configure your business operating hours
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SettingItem
                icon={Globe}
                title="Enable Business Hours"
                description="Restrict AI responses to business hours only"
              >
                <Switch
                  checked={settings.businessHoursEnabled}
                  onCheckedChange={(checked) => handleSettingChange('businessHoursEnabled', checked)}
                />
              </SettingItem>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="businessStartTime">Start Time</Label>
                  <Input
                    id="businessStartTime"
                    type="time"
                    value={settings.businessStartTime}
                    onChange={(e) => handleSettingChange('businessStartTime', e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="businessEndTime">End Time</Label>
                  <Input
                    id="businessEndTime"
                    type="time"
                    value={settings.businessEndTime}
                    onChange={(e) => handleSettingChange('businessEndTime', e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select value={settings.timezone} onValueChange={(value) => handleSettingChange('timezone', value)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="America/New_York">Eastern Time</SelectItem>
                      <SelectItem value="America/Chicago">Central Time</SelectItem>
                      <SelectItem value="America/Denver">Mountain Time</SelectItem>
                      <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                      <SelectItem value="UTC">UTC</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Shield className="h-5 w-5" />
                <span>Security Settings</span>
              </CardTitle>
              <CardDescription>
                Configure security and access controls
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SettingItem
                icon={Shield}
                title="Two-Factor Authentication"
                description="Add an extra layer of security to your account"
              >
                <Switch
                  checked={settings.twoFactorAuth}
                  onCheckedChange={(checked) => handleSettingChange('twoFactorAuth', checked)}
                />
              </SettingItem>

              <div>
                <Label htmlFor="sessionTimeout">Session Timeout (minutes)</Label>
                <Input
                  id="sessionTimeout"
                  type="number"
                  value={settings.sessionTimeout}
                  onChange={(e) => handleSettingChange('sessionTimeout', parseInt(e.target.value))}
                />
              </div>

              <div>
                <Label htmlFor="ipWhitelist">IP Whitelist</Label>
                <Textarea
                  id="ipWhitelist"
                  value={settings.ipWhitelist}
                  onChange={(e) => handleSettingChange('ipWhitelist', e.target.value)}
                  placeholder="Enter IP addresses (one per line)"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Integrations */}
        <TabsContent value="integrations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Database className="h-5 w-5" />
                <span>External Integrations</span>
              </CardTitle>
              <CardDescription>
                Configure connections to external services
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h4 className="font-medium mb-4">Shopify Integration</h4>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="shopifyStoreUrl">Store URL</Label>
                    <Input
                      id="shopifyStoreUrl"
                      value={settings.shopifyStoreUrl}
                      onChange={(e) => handleSettingChange('shopifyStoreUrl', e.target.value)}
                      placeholder="your-store.myshopify.com"
                    />
                  </div>
                  <div>
                    <Label htmlFor="shopifyApiKey">API Key</Label>
                    <Input
                      id="shopifyApiKey"
                      type="password"
                      value={settings.shopifyApiKey}
                      onChange={(e) => handleSettingChange('shopifyApiKey', e.target.value)}
                      placeholder="Enter your Shopify API key"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h4 className="font-medium mb-4">Shipping Integration</h4>
                <div>
                  <Label htmlFor="shippingApiKey">Shipping API Key</Label>
                  <Input
                    id="shippingApiKey"
                    type="password"
                    value={settings.shippingApiKey}
                    onChange={(e) => handleSettingChange('shippingApiKey', e.target.value)}
                    placeholder="Enter your shipping API key"
                  />
                </div>
              </div>

              <Separator />

              <SettingItem
                icon={SettingsIcon}
                title="Analytics Tracking"
                description="Enable detailed analytics and reporting"
              >
                <Switch
                  checked={settings.analyticsEnabled}
                  onCheckedChange={(checked) => handleSettingChange('analyticsEnabled', checked)}
                />
              </SettingItem>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

