*** End Patch
ReferenceAccountGreen Invoice uses JSON Web Tokens (JWT) to save session data (due to it's state-less characteristics), you can read more about JWT here.The session data will later allow us to identify your user.
Receiving a JWT Token using an API Key
Receiving a JWT Token using an API Key
This endpoint requires a generated API key that can be acquired through the Green Invoice website and is explained in here.This endpoint returns a JSON Web Token (JWT) in a header named X-Authorization-Bearer and in a field within a JSON called token.NOTE: The JSON Web Token (JWT) is valid for only a temporal time (currently for 1 hour), once a token becomes invalid, making requests for JWT required endpoints will result in a 401 Unauthorized error, and you will be required to request a new token.NOTE: The JSON Web Token (JWT) that is given by this endpoint includes information regarding the default business.Note for partners: When using partner keys, an extra request header Authorization is required with an input of Basic JWT (Where JWT is your partner Authorization code).To explain it even better, we made this general flowchart:Receiving a JWT Token using an API KeyAlso - this GIF will give you general idea on how to practically make the request (we used Postman):Receiving a JWT Token using an API Key-POSTMANReset Password
Reset Password
Sends an email to the user, with password reset instructions.
BusinessesBusinesses are a main component of Green Invoice system.Each business contains it's own documents, clients, items & settings.
Basic Business Actions
Get All User Businesses
Update a Business
Get Current Business
Get Current Business
Get Business By ID
Get Business By ID
Business Related Files
Upload Business Related Files
Upload business logo, signature, bookkeeping document, deduction document.NOTE:: The uploaded files need to be in Base64. The current allowed file types are: GIF, PNG, JPG, SVG, PDF.
Delete Business Related Files
Handling Documents NumberingWhen generating a document, the document receive a number, this number has to be unique for each document of the same type for accounting.Each document type starts from a different number.Some users that have migrated from other invoice systems might require to start from a different number in-order to keep their documents numbering intact & consecutive.
Get All Documents Numbering
Modify Initial Documents Numbering
This endpoint allows you to modify a document type initial numbering. Once modified and a first document of that type was generated - the document number will be locked for the specific type.Get Business Documents Footer
Get Business Documents Footer
NOTE: If no footer was set then the output will be an empty JSON.Get Business Types
Get Business Types
ClientsYou may add re-curring clients to your Green Invoice business user. This will allow you to add more information on the clients.The information can later be used to help you stay in touch with the clients and follow documents generated regarding their activities, as well as contact person, bank account and other information.
Add Client
Add Client
Adds a new client to the active business.Interacting with Existing Clients
Get Client
Update Client
Delete Client
NOTE: Only inactive clients can be deleted.Search Clients
Search Clients
Associate Existing Documents to a Client
Associate Existing Documents to a Client
Merge Clients
Merge Clients
NOTE: In-order to merge clients, one of them must be inactive. Once merged - the inactive client will be deleted and all his documents will be added to the merged client.Update Client Balance
Update Client Balance
Update the balance of a client.This endpoint will recalculate the final payment amount of a client by the given requested balance.To reset a client's balance - insert 0 as value.
SuppliersTo ease the process of entering the same supplier on multiple expenses you are able to create a supplier once and use it various times later while creating expenses.
Add Supplier
Add Supplier
Interacting with Existing Supplier
Get Supplier
Update Supplier
Delete Supplier
Search Suppliers
Search Suppliers
Merge Suppliers
Merge Suppliers
NOTE: In-order to merge suppliers, one of them must be inactive. Once merged - the inactive supplier will be deleted and all his documents will be added to the merged supplier.
ItemsWhile generating documents you are usually requested to add items.Items are products that are bought from you, it can be either a real product (such as electronic device, restaurant dish) or a virtual service (such as a programmer hour)..To ease the process of entering the same item on multiple documents you are able to create an item once and use it various times later while creating a document.
Add Item
Add Item
Interacting with Existing Items
Get Item
Update Item
Delete Item
Search Items
Search Items
DocumentsThe main component of the Green Invoice system is the documents, these documents can be of different types, such as but not only - order, invoice, receipt.Documents are business specific, and only the documents of the current used business are visible to you.
Add DocumentAdd a document to the current business.The document will be generated based on the default business & document settings, and by any overriding request attributes that we receive in this endpoint.NOTE: When declaring your vatType there's multiple different declarations. You can define the general vatType of the document, but - you can also define each income row vatType.NOTE: linkedDocumentIds allows you to state the related / relevant documents, e.g.: when creating a receipt, attach your original invoice document ID as one of the ids in the linkedDocumentIds - this in turn will automatically close the original invoice if needed.NOTE: linkedPaymentId allows you to define the paymentId that the document is going to be relevant to, this can be attached only to invoice documents (type 305).
Add Document
Get a Preview DocumentPreviews a document before the actual generation.This endpoint returns a file in Base64 format (you can read more about Base64 here).If you would like to view the file on your website there are build-in plugins to display PDF, other than that - if you would like to have a consistent user experience through all browsers (including mobile browsers) we would suggest using PDF.js (an amazing Mozilla library) is available and can view PDF from Base64 format.If you would like to add a download button for the preview in your website, here is a simple script to do that (do not forget to switch the {base64string} with the Base64 file that you received from the result):<a download="preview-document.pdf" href="data:application/pdf;base64,{base64string}">Download Preview</a>
NOTE: If you would like just to check how a preview file looks, use the string that was given in the file property from our server response, put it in the following website: https://www.freeformatter.com/base64-encoder.html and click DECODE AND DOWNLOAD. This will download the base64 string as a PDF file into your computer so that you can view it.
Get a Preview Document
Interacting with Existing Documents
Get Document
Search DocumentsSearch all generated documents (with possibility to filters).
Search Documents
Search Payments in DocumentsSearch payments in documents, using different filters.
Search Payments in Documents
Close Document
Close Document
Open Document
Open Document
Get Linked DocumentsGet information about linked / related documents to a specific document.
Get Linked Documents
Get Document Download LinksGet information about linked / related documents to a specific document.
Get Document Download Links
Get Document Type InformationGet information about specific document type.
Get Document Information
Get Document TemplatesRetrieves information regarding the available templates and their corresponding colors / skins in the system.
Get Document Templates
Get Document TypesRetrieve information regarding the available document types that are open for the current business.
Get Document Types
Get Document StatusesRetrieve information regarding the available document statuses.
Get Document Statuses
ExpensesExpenses allow you to track your records about outcome and to understand your cash flow better.
Add ExpenseAdd an expense to the current business.The expense will be generated based on the default business & document settings, and by any overriding request attributes that we receive in this endpoint.
Add Expense
Interacting with Existing Expenses
Get Expense
Update Expense
Delete Expense
Search ExpensesSearch all generated expenses (with possibility to filters).
Search Expenses
Open Expense
Open Expense
Close Expense
Close Expense
Get Allowed Expenses StatusesShows the expense statuses the selected business can use when interacting with the expenses endpoints.
Get Allowed Expenses Statuses
Get Accounting ClassificationsShows the accounting classifications that were defined for this business. The classification can be specified in the accountingClassification field when adding or updating an expense.
Get Accounting Classifications
Create an Expense Draft / Update an Existing Expense by FileWe have made changes to the way expense files are uploaded to enhance information security in our system. Therefore, from now on, every action used to upload files to the system (currently there are only two) will require two steps:Send a GET request to get a file upload URLUse attributes from the response of the previous request in order to upload the file by the relevant POST requestNOTE: These actions are asynchronous. Therefore, if you'd like to receive a notification of whether the action has been completed, you can set up a webhook (currently available only on the GUI) for the following events:'expense-draft/parsed' (for creating a new expense draft)'expense-file/updated' (for an updating an existing expense)'expense-draft/declined''file/infected'→ Use this guide to set up Webhooks.
Get File Upload URL
NOTE:The PRODUCTION URL is: https://apigw.greeninvoice.co.il/file-upload/v1/urlThe SANDBOX URL is: https://api.sandbox.d.greeninvoice.co.il/file-upload/v1/urlCode exampleNOTE: Referenced to the next actionsNOTE: we will upload the file to the response URL in the following way: the fields received will be added to the data sent see code example:interface File extends Blob { readonly name: string; }async uploadFile(file: File, headers: object): Promise<any> {
    const presignedPost = await this.getSignedUrl();
    const data = new FormData();
    Object.entries(presignedPost.fields).forEach(([field, value]) => {
        data.append(field, value);
    });
    
    data.append('file', file, file?.name);
    
    // make sure the headers contain 'Content-Type': 'multipart/form-data'
    return this.http.post(presignedPost.url, data, headers);
}
Add Expense Draft by File (Create Draft)
Add an expense draft to the current business.NOTES:Uploading a file always creates an expense draft - in order to generate an actual expense you need to "manually" approve the 'expense draft' after filling any required details.Use the url field you received in the response of the previous request (Get File Upload URL)
Update Expense File
NOTES:The expense could not be updated once reported (Expense status = 20)Use the url field you received in the response of the previous request (Get File Upload URL)Search Expense DraftsSearch all generated expense drafts (with possibility to filters).
Search Expense Drafts
PaymentsProvides interaction with our online invoice payments system.
Get Payment FormGet a payment form. This form can be used in an IFrame in your website to provide payment request abilities for invoices within websites.After the payment was made - the system will automatically generate a document for you.NOTE: Access to this endpoint is given only to accounts with one of the following clearing plugins:Cardcom (E-COMMERCE terminal type)IsracardDigital Payments (by Grow)NOTE: If you do not require the automatic creation of a document in our system - there is no need to use our payment system on your website, just use your favorite clearing company API directly.Payment Flow
Get Payment Form
Search Credit Card TokensSearch saved credit card tokens.
Search Credit Card Tokens
Charge Credit Card TokenCharge a credit card token. Document created data is returned.
Charge Credit Card Token
PartnersNOTES:Preforming actions in user accounts are restricted only for existing users in 'morning' with Best or higher subscriptions.Currently, partners are unable to create new user accounts.To use the partners endpoints you have to be a Green Invoice partner.A morning by Green Invoice partner can connect third-party application to Green Invoice and control connected users through his application.Once you are a Green Invoice partner you'll get an authorization code.As you can understand, in-order to work under a controlled user, there will be 3 steps:Request authorization from an existing morning by Green Invoice user. Doing so - will return a key which you should store and protect it from unauthorized access, the key - includes the user API key ID and API secret.Using your partner Authorization code you should then request a JSON Web Token (JWT) for that user, using /account/token endpoint.The last step is to use the user Authorization code that was received in the /account/token endpoint under other endpoints and basically - control your user.NOTE: An inactive partner account will result in 403 (Forbidden) status from the server.
Get Partner Users
Get All Connected Users
Gets all the connected and approved users.To get the user API keys related to your partner make a request using the user email with Get Connected User endpoint.Request User Approval
Request User Approval
Connect existing morning by Green Invoice user to partner.The user will then receive an email with request to approve the third-party connection.Once the user approves the request, you will get a JSON POST request notification to the callback url that you have specified in the url parameter you stated.This JSON POST notification will include the email that you requested to connect (so that you can identify to which user this key is relevant to).NOTE: The connection approval email that the user receives expires within 3 days, once this connection request expires and wasn't approved by the user - a new connection request must be initiated.SECURITY NOTE: You will also get a special header X-Data-Signature with the signed SHA256 value of the body using your partner auth token as the signature salt key, this can be used at your side to identify the credibility of the source once you receive the POST request notification. This validation is done by comparing the given X-Data-Signature data to the a self-encrypted JSON data (by applying the your partner Authorization code as salt using SHA256 on the received JSON). This step is not a must but a security measure that can be taken by you to forbid request forgeries. Examples of creating base64 hashes using HMAC SHA256 in different languages can be found hereNOTE: In our Postman collection we provide an example of the JSON POST notification that you will receive to your callback URL - you can use it for testing.To explain it even better, we made this flowchart:Request User Approval FlowchartGet Connected User
Get Connected User
Gets an already connected and approved user.This will return API keys of the user which are relevant only to your partner account.Disconnect Partner User
Disconnect Partner User
Removes a connected user from your partner.This will remove any partner related API keys from all the connected businesses of the user that was created and your will no longer be able to access it's resources.In case you are billed on this user, you will no longer pay on any future documents.Once the user is removed, the user will get a notification email regarding the disconnection.A disconnected partner user can reconnect at any time.NOTE: All of the businesses of the specified user that relates to your partner will be disconnected.
ToolsDifferent tools and objects resources that can be of help to you.The tools does not require a JWT token and are accessible to everyone for use.NOTE: The base URL is: https://cache.greeninvoice.co.il
Get Supported Business Categories
Get Supported Business Categories
Get the supported business categories and their sub categories.NOTES:The Endpoint URL is: https://cache.greeninvoice.co.il/businesses/v1/occupations?locale=he_ILThe locale=he_IL parameter is required.Get Supported Countries
Get Supported Countries
Get all countries supported ordered by alphabetical order.NOTES:The Endpoint URL is: https://cache.greeninvoice.co.il/geo-location/v1/countries?locale={locale}The locale parameter is required.Get Supported Cities
Get Supported Cities
Get all cities supported ordered by alphabetical order.NOTES:The Endpoint URL is: https://cache.greeninvoice.co.il/geo-location/v1/cities?locale={locale}&country=ILThe locale and country=IL parameters are required.Get Supported Currencies
Get Supported Currencies
Get the supported currencies. Retrieves the latest currency and the preivious day exchange rates by specified base currency.NOTES:The Endpoint URL is: https://cache.greeninvoice.co.il/currency-exchange/v1/latest?base={base}The base parameter is required.

No action selectedYou can try selecting 'Receiving a JWT Token using an API Key' from the left column.Learn more about using the documentation.